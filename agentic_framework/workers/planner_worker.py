"""Planner worker for task decomposition and planning."""

import asyncio
from typing import List, Optional, Type
import click
import structlog

from .base_worker import StatelessWorker, WorkerConfig, WorkerResult
from ..events.event_types import Event, TaskCreated, PlanCreated, WorkflowExecutionStarted
from ..events.aggregates import EventSourcedAggregate, EventSourcedTask
from ..planning.hybrid_planner import HybridPlanner
from ..planning.workflow import WorkflowStore
from ..planning.exceptions import ExceptionHandler, RetryPolicy


logger = structlog.get_logger()


class PlannerWorker(StatelessWorker):
    """Worker that handles task planning and decomposition."""
    
    def __init__(self, config: WorkerConfig):
        super().__init__(config)
        
        # Initialize planner components
        self.workflow_store = WorkflowStore(config.event_store_path)
        self.planner = HybridPlanner(self.workflow_store)
        
        # Mock team for planning (in real implementation, this would be retrieved from events)
        self._mock_team = self._create_mock_team()
    
    def _create_mock_team(self):
        """Create a mock team for planning purposes."""
        # This is a simplified mock - in a real implementation,
        # teams would be reconstructed from events
        class MockTeam:
            def __init__(self):
                self.id = "default-team"
                self.name = "Default Team"
        
        return MockTeam()
    
    async def process_event(self, event: Event, state: Optional[EventSourcedAggregate]) -> List[Event]:
        """Process planning-related events."""
        
        if event.event_type == "TaskCreated":
            return await self._handle_task_created(event, state)
        else:
            logger.warning(
                "Unhandled event type in planner",
                event_type=event.event_type,
                worker_id=self.config.worker_id
            )
            return []
    
    async def _handle_task_created(self, event: Event, state: Optional[EventSourcedTask]) -> List[Event]:
        """Handle TaskCreated events by creating execution plans."""
        
        if not state:
            logger.error("No task state available for planning", task_id=event.aggregate_id)
            return []
        
        try:
            logger.info(
                "Creating execution plan",
                task_id=event.aggregate_id,
                task_type=state.task_type,
                workflow_id=state.workflow_id
            )
            
            # Convert EventSourcedTask to Task for planning
            # (This is a simplification - in practice you might want a better conversion)
            from ..core.task import Task, TaskPriority
            
            task = Task(
                id=state.id,
                title=state.title,
                task_type=state.task_type,
                priority=TaskPriority(state.priority) if state.priority in [1,2,3,4] else TaskPriority.NORMAL,
                required_capabilities=state.required_capabilities,
                input_data=state.input_data,
                workflow_id=state.workflow_id
            )
            
            # Create execution plan
            execution_plan = await self.planner.create_execution_plan(task, self._mock_team)
            
            # Generate events based on plan type
            events = []
            
            if execution_plan.is_workflow_based():
                # Workflow-based plan
                logger.info(
                    "Created workflow-based plan",
                    task_id=task.id,
                    workflow_id=execution_plan.workflow_id,
                    execution_id=execution_plan.execution_id
                )
                
                # Add the pre-generated workflow events
                events.extend(execution_plan.events)
                
            else:
                # Agentic plan with task decomposition
                logger.info(
                    "Created agentic plan",
                    task_id=task.id,
                    subtasks_count=len(execution_plan.tasks),
                    dependencies=len(execution_plan.dependencies)
                )
                
                # Generate plan created event
                plan_event = PlanCreated(
                    plan_id=execution_plan.plan_id,
                    root_task_id=task.id,
                    tasks=[task_dict for task_dict in execution_plan.tasks.values()],
                    dependencies=execution_plan.dependencies,
                    metadata=execution_plan.metadata
                )
                events.append(plan_event)
                
                # Generate task assignment events for subtasks
                from ..events.event_types import TaskAssigned
                
                for task_id, team_id in execution_plan.team_assignments.items():
                    if task_id != task.id:  # Don't assign the root task to itself
                        task_assigned = TaskAssigned(
                            task_id=task_id,
                            assignee_id=team_id,
                            assignee_type="Team"
                        )
                        events.append(task_assigned)
            
            logger.info(
                "Execution plan completed",
                task_id=task.id,
                plan_type=execution_plan.plan_type,
                events_generated=len(events)
            )
            
            return events
            
        except Exception as e:
            logger.error(
                "Failed to create execution plan",
                task_id=event.aggregate_id,
                error=str(e)
            )
            
            # Generate task failure event
            from ..events.event_types import TaskFailed
            task_failed = TaskFailed(
                task_id=event.aggregate_id,
                error_message=f"Planning failed: {str(e)}",
                executor_id=f"planner-{self.config.worker_id}"
            )
            
            return [task_failed]
    
    # StatelessWorker interface implementation
    
    async def _can_process_event(self, event: Event, state: Optional[EventSourcedAggregate]) -> bool:
        """Check if this worker can process the event."""
        return event.event_type == "TaskCreated"
    
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
        # Planning events usually trigger task execution
        return event.event_type in ["WorkflowStepScheduled", "TaskAssigned"]
    
    async def _get_exception_handlers(self, event: Event) -> List[ExceptionHandler]:
        """Get exception handlers for the event."""
        return [
            ExceptionHandler(
                exception_types=["*"],
                strategy="retry",
                retry_policy=RetryPolicy(max_attempts=2, initial_delay_ms=2000)
            )
        ]
    
    def get_supported_event_types(self) -> List[str]:
        """Get supported event types."""
        return ["TaskCreated"]
    
    def get_worker_type(self) -> str:
        """Get worker type."""
        return "Planner"


@click.command()
@click.option('--worker-id', required=True, help='Worker ID')
@click.option('--sqlite-path', default='events.db', help='SQLite database path')
@click.option('--redis-url', default='redis://localhost:6379', help='Redis URL')
@click.option('--detach', is_flag=True, help='Run in detached mode')
async def main(worker_id, sqlite_path, redis_url, detach):
    """Run the planner worker."""
    
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
    
    worker = PlannerWorker(config)
    
    try:
        await worker.initialize()
        
        logger.info("Planner worker started", worker_id=worker_id)
        
        # Main worker loop
        while True:
            try:
                # Pull work item from queue  
                work_item = await worker.message_bus.pop_from_queue("work_queue", timeout=30)
                
                if work_item:
                    # Only process TaskCreated events
                    if work_item.get("event_type") != "TaskCreated":
                        continue
                    
                    # Convert work item to Event
                    from datetime import datetime
                    event = Event(
                        event_id=work_item["event_id"],
                        event_type=work_item["event_type"],
                        aggregate_id=work_item["aggregate_id"],
                        aggregate_type=work_item["aggregate_type"],
                        payload=work_item["payload"],
                        metadata=work_item["metadata"],
                        timestamp=datetime.fromisoformat(work_item["timestamp"]),
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
                logger.error("Error in planner worker loop", error=str(e))
                await asyncio.sleep(5)  # Back off on error
        
    except Exception as e:
        logger.error("Planner worker failed", error=str(e))
        return 1
    finally:
        await worker.shutdown()
    
    logger.info("Planner worker stopped")
    return 0


if __name__ == '__main__':
    import sys
    
    # Add async support
    def async_main():
        return asyncio.run(main(standalone_mode=False))
    
    sys.exit(async_main())