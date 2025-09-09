"""Worker spawner for managing stateless worker processes."""

import asyncio
import subprocess
import signal
import sys
import os
from typing import Dict, List, Optional, Set
from uuid import uuid4
from datetime import datetime, timezone
import structlog

from ..messaging.hybrid_bus import HybridMessageBus
from ..events.event_types import Event


logger = structlog.get_logger()


class WorkerSpawner:
    """Manages spawning and lifecycle of stateless worker processes."""
    
    def __init__(self, sqlite_path: str = "events.db", redis_url: str = "redis://localhost:6379"):
        self.sqlite_path = sqlite_path
        self.redis_url = redis_url
        self.bus = HybridMessageBus(sqlite_path=sqlite_path, redis_url=redis_url)
        
        # Process tracking
        self._worker_processes: Dict[str, subprocess.Popen] = {}
        self._worker_types: Dict[str, str] = {}
        self._running = False
        
        # Worker type mapping
        self._worker_commands = {
            "planner": [sys.executable, "-m", "agentic_framework.workers.planner_worker"],
            "executor": [sys.executable, "-m", "agentic_framework.workers.task_worker"],  
            "workflow": [sys.executable, "-m", "agentic_framework.workers.workflow_worker"],
            "monitor": [sys.executable, "-m", "agentic_framework.workers.monitor_worker"]
        }
    
    async def initialize(self) -> None:
        """Initialize the spawner."""
        await self.bus.connect()
        self._running = True
        logger.info("Worker spawner initialized")
    
    async def shutdown(self) -> None:
        """Shutdown the spawner and all workers."""
        self._running = False
        
        # Stop all workers
        worker_ids = list(self._worker_processes.keys())
        await self.stop_workers(worker_ids)
        
        await self.bus.disconnect()
        logger.info("Worker spawner shut down")
    
    async def spawn_worker(
        self, 
        worker_type: str = "executor", 
        worker_id: Optional[str] = None,
        detach: bool = False
    ) -> str:
        """Spawn a new worker process."""
        
        if worker_id is None:
            worker_id = f"{worker_type}-{str(uuid4())[:8]}"
        
        if worker_type == "all":
            # Spawn one of each type
            spawned_ids = []
            for wtype in ["planner", "executor", "workflow"]:
                wid = await self.spawn_worker(wtype, detach=detach)
                spawned_ids.append(wid)
            return ",".join(spawned_ids)
        
        if worker_type not in self._worker_commands:
            raise ValueError(f"Unknown worker type: {worker_type}")
        
        try:
            # Build command
            cmd = self._worker_commands[worker_type].copy()
            
            # Add configuration arguments
            cmd.extend([
                "--worker-id", worker_id,
                "--sqlite-path", self.sqlite_path,
                "--redis-url", self.redis_url
            ])
            
            if detach:
                cmd.append("--detach")
            
            # Set up environment
            env = os.environ.copy()
            env["PYTHONPATH"] = os.getcwd()
            
            # Start the process
            if detach:
                # Detached mode - process continues after spawner exits
                process = subprocess.Popen(
                    cmd,
                    env=env,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    preexec_fn=os.setsid  # Create new process group
                )
            else:
                # Attached mode - spawner manages the process
                process = subprocess.Popen(
                    cmd,
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
            
            # Track the process
            self._worker_processes[worker_id] = process
            self._worker_types[worker_id] = worker_type
            
            logger.info(
                "Worker spawned",
                worker_id=worker_id,
                worker_type=worker_type,
                pid=process.pid,
                detached=detach
            )
            
            return worker_id
            
        except Exception as e:
            logger.error(
                "Failed to spawn worker",
                worker_id=worker_id,
                worker_type=worker_type,
                error=str(e)
            )
            raise
    
    async def stop_worker(self, worker_id: str, timeout: int = 30) -> bool:
        """Stop a specific worker."""
        
        if worker_id not in self._worker_processes:
            logger.warning("Worker not found", worker_id=worker_id)
            return False
        
        process = self._worker_processes[worker_id]
        worker_type = self._worker_types[worker_id]
        
        try:
            logger.info(
                "Stopping worker",
                worker_id=worker_id,
                worker_type=worker_type,
                pid=process.pid
            )
            
            # Try graceful shutdown first
            process.send_signal(signal.SIGTERM)
            
            # Wait for graceful shutdown
            try:
                process.wait(timeout=timeout)
                logger.info("Worker stopped gracefully", worker_id=worker_id)
            except subprocess.TimeoutExpired:
                # Force kill if graceful shutdown failed
                logger.warning("Force killing worker", worker_id=worker_id)
                process.kill()
                process.wait()
            
            # Clean up tracking
            del self._worker_processes[worker_id]
            del self._worker_types[worker_id]
            
            return True
            
        except Exception as e:
            logger.error(
                "Error stopping worker",
                worker_id=worker_id,
                error=str(e)
            )
            return False
    
    async def stop_workers(self, worker_ids: List[str]) -> Dict[str, bool]:
        """Stop multiple workers."""
        results = {}
        
        # Stop all workers concurrently
        tasks = [self.stop_worker(worker_id) for worker_id in worker_ids]
        stop_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for worker_id, result in zip(worker_ids, stop_results):
            if isinstance(result, Exception):
                logger.error("Exception stopping worker", worker_id=worker_id, error=str(result))
                results[worker_id] = False
            else:
                results[worker_id] = result
        
        return results
    
    async def wait_for_workers(self, worker_ids: List[str]) -> Dict[str, int]:
        """Wait for workers to complete and return their exit codes."""
        results = {}
        
        for worker_id in worker_ids:
            if worker_id not in self._worker_processes:
                results[worker_id] = -1
                continue
            
            try:
                process = self._worker_processes[worker_id]
                exit_code = process.wait()
                results[worker_id] = exit_code
                
                logger.info(
                    "Worker completed",
                    worker_id=worker_id,
                    exit_code=exit_code
                )
                
                # Clean up tracking
                del self._worker_processes[worker_id]
                del self._worker_types[worker_id]
                
            except Exception as e:
                logger.error(
                    "Error waiting for worker",
                    worker_id=worker_id,
                    error=str(e)
                )
                results[worker_id] = -1
        
        return results
    
    async def auto_scale_workers(
        self,
        target_queue_length: int = 10,
        max_workers: int = 10,
        scale_up_threshold: int = 20,
        scale_down_threshold: int = 5
    ) -> None:
        """Automatically scale workers based on queue length."""
        
        if not self._running:
            return
        
        try:
            queue_length = await self.bus.get_work_queue_length()
            current_workers = len(self._worker_processes)
            
            logger.debug(
                "Auto-scaling check",
                queue_length=queue_length,
                current_workers=current_workers,
                target_queue_length=target_queue_length
            )
            
            if queue_length > scale_up_threshold and current_workers < max_workers:
                # Scale up
                new_workers = min(
                    max_workers - current_workers,
                    (queue_length // target_queue_length) + 1
                )
                
                logger.info(
                    "Scaling up workers",
                    queue_length=queue_length,
                    current_workers=current_workers,
                    new_workers=new_workers
                )
                
                for _ in range(new_workers):
                    await self.spawn_worker("executor", detach=True)
            
            elif queue_length < scale_down_threshold and current_workers > 1:
                # Scale down (but keep at least one worker)
                excess_workers = current_workers - max(1, queue_length // target_queue_length)
                
                if excess_workers > 0:
                    logger.info(
                        "Scaling down workers",
                        queue_length=queue_length,
                        current_workers=current_workers,
                        removing_workers=excess_workers
                    )
                    
                    # Stop oldest workers
                    worker_ids_to_stop = list(self._worker_processes.keys())[:excess_workers]
                    await self.stop_workers(worker_ids_to_stop)
            
        except Exception as e:
            logger.error("Error in auto-scaling", error=str(e))
    
    async def run_auto_scaler(
        self,
        check_interval: int = 30,
        target_queue_length: int = 10,
        max_workers: int = 10
    ) -> None:
        """Run auto-scaling loop."""
        
        logger.info(
            "Starting auto-scaler",
            check_interval=check_interval,
            target_queue_length=target_queue_length,
            max_workers=max_workers
        )
        
        while self._running:
            try:
                await self.auto_scale_workers(
                    target_queue_length=target_queue_length,
                    max_workers=max_workers
                )
                
                await asyncio.sleep(check_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in auto-scaler loop", error=str(e))
                await asyncio.sleep(check_interval)
        
        logger.info("Auto-scaler stopped")
    
    def get_worker_status(self) -> Dict[str, Dict]:
        """Get status of all tracked workers."""
        status = {}
        
        for worker_id, process in self._worker_processes.items():
            worker_type = self._worker_types.get(worker_id, "unknown")
            
            # Check if process is still running
            poll_result = process.poll()
            is_running = poll_result is None
            
            status[worker_id] = {
                "type": worker_type,
                "pid": process.pid,
                "running": is_running,
                "exit_code": poll_result
            }
        
        return status
    
    async def health_check(self) -> Dict[str, any]:
        """Perform health check on spawner and workers."""
        try:
            queue_length = await self.bus.get_work_queue_length()
            worker_status = self.get_worker_status()
            
            # Count running workers by type
            running_by_type = {}
            for worker_info in worker_status.values():
                if worker_info["running"]:
                    wtype = worker_info["type"]
                    running_by_type[wtype] = running_by_type.get(wtype, 0) + 1
            
            return {
                "spawner_running": self._running,
                "total_workers": len(self._worker_processes),
                "running_workers": sum(1 for w in worker_status.values() if w["running"]),
                "workers_by_type": running_by_type,
                "queue_length": queue_length,
                "worker_details": worker_status
            }
            
        except Exception as e:
            return {"error": str(e)}


# Signal handler for graceful shutdown
def setup_signal_handlers(spawner: WorkerSpawner):
    """Set up signal handlers for graceful shutdown."""
    
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")
        asyncio.create_task(spawner.shutdown())
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)