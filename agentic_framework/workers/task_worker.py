"""Task executor worker for processing individual tasks."""

import asyncio
from typing import List, Optional, Type
import click
import structlog

from .base_worker import StatelessWorker, WorkerConfig, WorkerResult
from ..events.event_types import Event, TaskCreated, TaskAssigned, TaskStarted, TaskCompleted, TaskFailed
from ..events.aggregates import EventSourcedAggregate, EventSourcedTask
from ..planning.exceptions import ExceptionHandler, RetryPolicy


logger = structlog.get_logger()


class TaskExecutorWorker(StatelessWorker):
    """Worker that executes individual tasks."""
    
    def __init__(self, config: WorkerConfig):
        super().__init__(config)
        
        # Task handlers - in a real implementation, these would be more sophisticated
        self._task_handlers = {
            "data_processing": self._handle_data_processing,
            "analysis": self._handle_analysis,
            "reporting": self._handle_reporting,
            "generic": self._handle_generic_task
        }
    
    async def process_event(self, event: Event, state: Optional[EventSourcedAggregate]) -> List[Event]:
        """Process task-related events."""
        
        if event.event_type == "TaskCreated":
            return await self._handle_task_created(event, state)
        elif event.event_type == "TaskAssigned":
            return await self._handle_task_assigned(event, state)
        else:
            logger.warning(
                "Unhandled event type",
                event_type=event.event_type,
                worker_id=self.config.worker_id
            )
            return []
    
    async def _handle_task_created(self, event: Event, state: Optional[EventSourcedTask]) -> List[Event]:
        """Handle TaskCreated events by assigning to appropriate executor."""
        
        # In a real implementation, this would use team/agent discovery
        # For now, we'll auto-assign to a generic executor
        
        task_assigned = TaskAssigned(
            task_id=event.aggregate_id,
            assignee_id=f"executor-{self.config.worker_id}",
            assignee_type="Agent"
        )
        
        logger.info(
            "Task auto-assigned",
            task_id=event.aggregate_id,
            assignee_id=task_assigned.payload["assignee_id"]
        )
        
        return [task_assigned]
    
    async def _handle_task_assigned(self, event: Event, state: Optional[EventSourcedTask]) -> List[Event]:
        """Handle TaskAssigned events by starting task execution."""
        
        if not state:
            logger.error("No task state available for assignment", task_id=event.aggregate_id)
            return []
        
        # Check if we should execute this task
        assignee_id = event.payload.get("assignee_id")
        if not assignee_id or not assignee_id.startswith(f"executor-{self.config.worker_id}"):
            # Not assigned to us
            return []
        
        # Start task execution
        task_started = TaskStarted(
            task_id=event.aggregate_id,
            executor_id=assignee_id
        )
        
        logger.info(
            "Starting task execution",
            task_id=event.aggregate_id,
            task_type=state.task_type,
            executor_id=assignee_id
        )
        
        # Execute the task
        try:
            result = await self._execute_task(state)
            
            task_completed = TaskCompleted(
                task_id=event.aggregate_id,
                result=result,
                executor_id=assignee_id
            )
            
            logger.info(
                "Task execution completed",
                task_id=event.aggregate_id,
                result_keys=list(result.keys())
            )
            
            return [task_started, task_completed]
            
        except Exception as e:
            task_failed = TaskFailed(
                task_id=event.aggregate_id,
                error_message=str(e),
                executor_id=assignee_id
            )
            
            logger.error(
                "Task execution failed",
                task_id=event.aggregate_id,
                error=str(e)
            )
            
            return [task_started, task_failed]
    
    async def _execute_task(self, task: EventSourcedTask) -> dict:
        """Execute the actual task logic."""
        
        # Get task handler
        handler = self._task_handlers.get(task.task_type, self._task_handlers["generic"])
        
        # Execute with timeout
        result = await asyncio.wait_for(
            handler(task),
            timeout=300  # 5 minute timeout
        )
        
        return result
    
    async def _handle_data_processing(self, task: EventSourcedTask) -> dict:
        """Handle data processing tasks."""
        
        logger.info("Processing data", task_id=task.id)
        
        # Simulate data processing work
        await asyncio.sleep(2)
        
        return {
            "processed_records": 1000,
            "processing_time_ms": 2000,
            "output_format": "json",
            "status": "completed"
        }
    
    async def _handle_analysis(self, task: EventSourcedTask) -> dict:
        """Handle analysis tasks."""
        
        logger.info("Performing analysis", task_id=task.id)
        
        # Simulate analysis work
        await asyncio.sleep(3)
        
        return {
            "analysis_type": "statistical",
            "metrics": {
                "mean": 42.7,
                "std_dev": 8.3,
                "count": 1000
            },
            "confidence": 0.95,
            "status": "completed"
        }
    
    async def _handle_reporting(self, task: EventSourcedTask) -> dict:
        """Handle reporting tasks."""
        
        logger.info("Generating report", task_id=task.id)
        
        # Simulate report generation
        await asyncio.sleep(1)
        
        return {
            "report_type": "summary",
            "pages": 5,
            "format": "pdf",
            "file_size_mb": 2.3,
            "status": "completed"
        }
    
    async def _handle_generic_task(self, task: EventSourcedTask) -> dict:
        """Handle generic tasks."""
        
        logger.info("Processing generic task", task_id=task.id, task_type=task.task_type)
        
        # Simulate generic work
        await asyncio.sleep(1)
        
        return {
            "task_type": task.task_type,
            "input_data_size": len(str(task.input_data)),
            "processing_method": "generic",
            "status": "completed"
        }
    
    # StatelessWorker interface implementation
    
    async def _can_process_event(self, event: Event, state: Optional[EventSourcedAggregate]) -> bool:
        """Check if this worker can process the event."""
        return event.event_type in ["TaskCreated", "TaskAssigned"]
    
    async def _requires_state_reconstruction(self, event: Event) -> bool:
        """Check if state reconstruction is needed."""
        return event.aggregate_type == "Task"
    
    async def _get_aggregate_class(self, aggregate_type: str) -> Optional[Type[EventSourcedAggregate]]:
        """Get the aggregate class for the given type."""
        if aggregate_type == "Task":
            return EventSourcedTask
        return None
    
    async def _requires_processing(self, event: Event) -> bool:
        """Check if the event requires further processing."""
        # Task events might trigger further workflow steps
        return event.event_type in ["TaskCompleted", "TaskFailed"]
    
    async def _get_exception_handlers(self, event: Event) -> List[ExceptionHandler]:
        """Get exception handlers for the event."""
        return [
            ExceptionHandler(
                exception_types=["*"],
                strategy="retry",
                retry_policy=RetryPolicy(max_attempts=3, initial_delay_ms=1000)
            )
        ]
    
    def get_supported_event_types(self) -> List[str]:
        """Get supported event types."""
        return ["TaskCreated", "TaskAssigned"]
    
    def get_worker_type(self) -> str:
        """Get worker type."""
        return "TaskExecutor"


@click.command()
@click.option('--worker-id', required=True, help='Worker ID')
@click.option('--sqlite-path', default='events.db', help='SQLite database path')
@click.option('--redis-url', default='redis://localhost:6379', help='Redis URL')
@click.option('--detach', is_flag=True, help='Run in detached mode')
async def main(worker_id, sqlite_path, redis_url, detach):
    """Run the task executor worker."""
    
    # Configure logging
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="ISO"),
            structlog.dev.ConsoleRenderer()
        ],
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True
    )
    
    config = WorkerConfig(
        worker_id=worker_id,
        event_store_path=sqlite_path,
        redis_url=redis_url
    )
    
    worker = TaskExecutorWorker(config)
    
    try:
        await worker.initialize()
        
        logger.info("Task executor worker started", worker_id=worker_id)
        
        # Main worker loop
        while True:
            try:
                # Pull work item from queue
                work_item = await worker.message_bus.pop_from_queue("work_queue", timeout=30)
                
                if work_item:
                    # Convert work item to Event
                    event = Event(
                        event_id=work_item["event_id"],
                        event_type=work_item["event_type"],
                        aggregate_id=work_item["aggregate_id"],
                        aggregate_type=work_item["aggregate_type"],
                        payload=work_item["payload"],
                        metadata=work_item["metadata"],
                        timestamp=work_item["timestamp"],
                        sequence_number=work_item["sequence_number"]
                    )
                    
                    # Process the event
                    result = await worker.run_once(event)
                    
                    if not result.success and result.should_retry:
                        # Re-queue for retry after delay
                        await asyncio.sleep(result.retry_delay_ms / 1000)
                        await worker.message_bus.push_to_queue("work_queue", work_item)
                        
                        logger.info(
                            "Event requeued for retry",
                            event_id=event.event_id,
                            retry_delay_ms=result.retry_delay_ms
                        )
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error("Error in worker loop", error=str(e))
                await asyncio.sleep(5)  # Back off on error
        
    except Exception as e:
        logger.error("Worker failed", error=str(e))
        return 1
    finally:
        await worker.shutdown()
    
    logger.info("Task executor worker stopped")
    return 0


if __name__ == '__main__':
    import sys
    
    # Add async support
    def async_main():
        return asyncio.run(main(standalone_mode=False))
    
    sys.exit(async_main())