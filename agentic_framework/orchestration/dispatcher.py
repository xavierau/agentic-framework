"""Task dispatching and work distribution."""

import asyncio
from typing import Dict, List, Optional, Set
from datetime import datetime, timedelta
import structlog

from ..core.task import Task, TaskStatus
from ..core.team import Team
from ..messaging.base import MessageBus, Message, MessageType
from .planner import ExecutionPlan


logger = structlog.get_logger()


class TaskDispatcher:
    """Handles task distribution and execution coordination."""
    
    def __init__(self, message_bus: MessageBus):
        self.message_bus = message_bus
        self._team_registry: Dict[str, Team] = {}
        self._active_plans: Dict[str, ExecutionPlan] = {}
        self._task_status: Dict[str, TaskStatus] = {}
        self._running = False
    
    def register_team(self, team: Team) -> None:
        """Register a team for task dispatching."""
        self._team_registry[team.id] = team
    
    async def start(self) -> None:
        """Start the task dispatcher."""
        if self._running:
            return
            
        self._running = True
        
        # Subscribe to task completion messages
        await self.message_bus.subscribe("task.completed", self._handle_task_completion)
        await self.message_bus.subscribe("task.failed", self._handle_task_failure)
        
        # Start the dispatch loop
        asyncio.create_task(self._dispatch_loop())
        
        logger.info("Task dispatcher started")
    
    async def stop(self) -> None:
        """Stop the task dispatcher."""
        self._running = False
        
        await self.message_bus.unsubscribe("task.completed")
        await self.message_bus.unsubscribe("task.failed")
        
        logger.info("Task dispatcher stopped")
    
    async def execute_plan(self, plan: ExecutionPlan) -> str:
        """Execute an execution plan."""
        self._active_plans[plan.root_task_id] = plan
        
        # Initialize task status
        for task_id, task in plan.tasks.items():
            self._task_status[task_id] = task.status
        
        # Start dispatching tasks
        await self._dispatch_ready_tasks(plan)
        
        logger.info(
            "Plan execution started",
            root_task_id=plan.root_task_id,
            total_tasks=len(plan.tasks)
        )
        
        return plan.root_task_id
    
    async def _dispatch_loop(self) -> None:
        """Main dispatch loop to handle ongoing task execution."""
        while self._running:
            try:
                # Check all active plans for ready tasks
                for plan_id, plan in list(self._active_plans.items()):
                    if plan.is_complete():
                        await self._complete_plan(plan_id)
                        continue
                    
                    await self._dispatch_ready_tasks(plan)
                
                await asyncio.sleep(1)  # Check every second
                
            except Exception as e:
                logger.error("Error in dispatch loop", error=str(e))
                await asyncio.sleep(5)  # Back off on error
    
    async def _dispatch_ready_tasks(self, plan: ExecutionPlan) -> None:
        """Dispatch tasks that are ready to execute."""
        completed_tasks = {
            task_id for task_id, status in self._task_status.items()
            if status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]
        }
        
        ready_task_ids = plan.get_ready_tasks(completed_tasks)
        
        for task_id in ready_task_ids:
            if self._task_status.get(task_id) == TaskStatus.PENDING:
                task = plan.tasks[task_id]
                team_id = plan.team_assignments.get(task_id)
                
                if team_id and team_id in self._team_registry:
                    team = self._team_registry[team_id]
                    success = await self._dispatch_task_to_team(task, team)
                    
                    if success:
                        self._task_status[task_id] = TaskStatus.IN_PROGRESS
                        logger.info(
                            "Task dispatched",
                            task_id=task_id,
                            team_id=team_id,
                            plan_id=plan.root_task_id
                        )
                    else:
                        logger.warning(
                            "Failed to dispatch task",
                            task_id=task_id,
                            team_id=team_id
                        )
    
    async def _dispatch_task_to_team(self, task: Task, team: Team) -> bool:
        """Dispatch a task to a specific team."""
        try:
            # Send task request to team
            message = Message.create(
                sender_id="dispatcher",
                receiver_id=team.id,
                message_type=MessageType.TEAM_TASK_REQUEST,
                content={"task": task.to_dict()},
                task_id=task.id,
                team_id=team.id
            )
            
            await self.message_bus.send_to_team(team.id, message)
            return True
            
        except Exception as e:
            logger.error(
                "Error dispatching task to team",
                task_id=task.id,
                team_id=team.id,
                error=str(e)
            )
            return False
    
    async def _handle_task_completion(self, message: Message) -> None:
        """Handle task completion notifications."""
        try:
            task_id = message.content.get("task_id")
            if not task_id:
                return
            
            self._task_status[task_id] = TaskStatus.COMPLETED
            
            # Update the task in active plans
            for plan in self._active_plans.values():
                if task_id in plan.tasks:
                    task = plan.tasks[task_id]
                    result_data = message.content.get("result", {})
                    
                    if result_data:
                        from ..core.task import TaskResult
                        task.result = TaskResult(**result_data)
                    
                    task.status = TaskStatus.COMPLETED
                    task.completed_at = datetime.utcnow()
                    
                    logger.info(
                        "Task completion handled",
                        task_id=task_id,
                        plan_id=plan.root_task_id
                    )
                    break
            
        except Exception as e:
            logger.error("Error handling task completion", error=str(e))
    
    async def _handle_task_failure(self, message: Message) -> None:
        """Handle task failure notifications."""
        try:
            task_id = message.content.get("task_id")
            if not task_id:
                return
            
            self._task_status[task_id] = TaskStatus.FAILED
            
            # Update the task in active plans
            for plan in self._active_plans.values():
                if task_id in plan.tasks:
                    task = plan.tasks[task_id]
                    result_data = message.content.get("result", {})
                    
                    if result_data:
                        from ..core.task import TaskResult
                        task.result = TaskResult(**result_data)
                    
                    task.status = TaskStatus.FAILED
                    task.completed_at = datetime.utcnow()
                    
                    # Decide whether to retry or fail dependent tasks
                    await self._handle_task_failure_cascading(plan, task_id)
                    
                    logger.warning(
                        "Task failure handled",
                        task_id=task_id,
                        plan_id=plan.root_task_id
                    )
                    break
            
        except Exception as e:
            logger.error("Error handling task failure", error=str(e))
    
    async def _handle_task_failure_cascading(self, plan: ExecutionPlan, failed_task_id: str) -> None:
        """Handle cascading effects of task failure."""
        # Find tasks that depend on the failed task
        dependent_tasks = [
            task_id for task_id, deps in plan.dependencies.items()
            if failed_task_id in deps
        ]
        
        for task_id in dependent_tasks:
            if self._task_status.get(task_id) == TaskStatus.PENDING:
                # Cancel dependent tasks that haven't started yet
                self._task_status[task_id] = TaskStatus.CANCELLED
                task = plan.tasks[task_id]
                task.cancel(f"Dependency {failed_task_id} failed")
                
                logger.info(
                    "Task cancelled due to dependency failure",
                    task_id=task_id,
                    failed_dependency=failed_task_id
                )
    
    async def _complete_plan(self, plan_id: str) -> None:
        """Complete execution of a plan."""
        plan = self._active_plans.pop(plan_id, None)
        if not plan:
            return
        
        # Calculate plan statistics
        total_tasks = len(plan.tasks)
        completed_tasks = sum(1 for status in self._task_status.values() 
                            if status == TaskStatus.COMPLETED)
        failed_tasks = sum(1 for status in self._task_status.values() 
                         if status == TaskStatus.FAILED)
        cancelled_tasks = sum(1 for status in self._task_status.values() 
                            if status == TaskStatus.CANCELLED)
        
        # Send plan completion notification
        message = Message.create(
            sender_id="dispatcher",
            message_type=MessageType.PLAN_UPDATED,
            content={
                "plan_id": plan_id,
                "status": "completed",
                "total_tasks": total_tasks,
                "completed_tasks": completed_tasks,
                "failed_tasks": failed_tasks,
                "cancelled_tasks": cancelled_tasks,
            }
        )
        
        await self.message_bus.publish("system.plan_completion", message)
        
        logger.info(
            "Plan execution completed",
            plan_id=plan_id,
            total_tasks=total_tasks,
            completed=completed_tasks,
            failed=failed_tasks,
            cancelled=cancelled_tasks
        )
    
    def get_plan_status(self, plan_id: str) -> Optional[Dict[str, any]]:
        """Get the status of a plan."""
        plan = self._active_plans.get(plan_id)
        if not plan:
            return None
        
        task_statuses = {}
        for task_id in plan.tasks:
            task_statuses[task_id] = self._task_status.get(task_id, TaskStatus.PENDING)
        
        return {
            "plan_id": plan_id,
            "root_task_id": plan.root_task_id,
            "total_tasks": len(plan.tasks),
            "task_statuses": task_statuses,
            "is_complete": plan.is_complete(),
        }
    
    def get_active_plans(self) -> List[str]:
        """Get list of active plan IDs."""
        return list(self._active_plans.keys())