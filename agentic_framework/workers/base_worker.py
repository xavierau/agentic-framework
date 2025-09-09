"""Base class for stateless workers in the agentic framework."""

import asyncio
import traceback
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, Type
from datetime import datetime, timezone
from pydantic import BaseModel
import structlog

from ..events.event_store import EventStore, SQLiteEventStore
from ..events.event_types import Event
from ..events.aggregates import EventSourcedAggregate  
from ..messaging.redis_bus import RedisMessageBus
from ..planning.exceptions import ExceptionHandlingEngine, ExceptionHandler


logger = structlog.get_logger()


class WorkerResult(BaseModel):
    """Result of worker processing."""
    
    success: bool
    events_generated: List[Event] = []
    should_retry: bool = False
    retry_delay_ms: int = 0
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = {}


class WorkerConfig(BaseModel):
    """Configuration for a worker."""
    
    worker_id: str
    event_store_path: str = "events.db"
    redis_url: str = "redis://localhost:6379"
    max_processing_time_ms: int = 300000  # 5 minutes
    enable_snapshots: bool = True
    snapshot_frequency: int = 10  # Save snapshot every 10 events
    

class StatelessWorker(ABC):
    """
    Base class for stateless workers that process events.
    
    Workers follow this pattern:
    1. Pull event from message queue
    2. Reconstruct state from event store
    3. Process the event
    4. Generate new events
    5. Persist events to store
    6. Dispatch events to message bus
    7. Terminate safely
    """
    
    def __init__(self, config: WorkerConfig):
        self.config = config
        self.event_store = SQLiteEventStore(config.event_store_path)
        self.message_bus = RedisMessageBus(config.redis_url)
        self.exception_handler = ExceptionHandlingEngine()
        
        # Worker state (minimal)
        self._running = False
        self._processed_count = 0
    
    async def initialize(self) -> None:
        """Initialize worker components."""
        try:
            await self.event_store.initialize()
            await self.message_bus.connect()
            logger.info("Worker initialized", worker_id=self.config.worker_id)
        except Exception as e:
            logger.error(
                "Worker initialization failed",
                worker_id=self.config.worker_id,
                error=str(e)
            )
            raise
    
    async def shutdown(self) -> None:
        """Shutdown worker components."""
        try:
            await self.message_bus.disconnect()
            logger.info(
                "Worker shut down",
                worker_id=self.config.worker_id,
                processed_count=self._processed_count
            )
        except Exception as e:
            logger.error(
                "Worker shutdown error",
                worker_id=self.config.worker_id,
                error=str(e)
            )
    
    async def run_once(self, event: Event) -> WorkerResult:
        """
        Process a single event and return the result.
        This is the main entry point for stateless processing.
        """
        start_time = datetime.now(timezone.utc)
        
        logger.info(
            "Processing event",
            worker_id=self.config.worker_id,
            event_id=event.event_id,
            event_type=event.event_type,
            aggregate_id=event.aggregate_id
        )
        
        try:
            # Set processing timeout
            return await asyncio.wait_for(
                self._process_event_with_error_handling(event),
                timeout=self.config.max_processing_time_ms / 1000
            )
            
        except asyncio.TimeoutError:
            error_msg = f"Worker processing timed out after {self.config.max_processing_time_ms}ms"
            logger.error(error_msg, worker_id=self.config.worker_id, event_id=event.event_id)
            return WorkerResult(
                success=False,
                error_message=error_msg,
                metadata={"timeout": True}
            )
        except Exception as e:
            logger.error(
                "Unexpected error in worker",
                worker_id=self.config.worker_id,
                event_id=event.event_id,
                error=str(e),
                traceback=traceback.format_exc()
            )
            return WorkerResult(
                success=False,
                error_message=f"Unexpected worker error: {str(e)}",
                metadata={"unexpected_error": True}
            )
        finally:
            processing_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            logger.info(
                "Event processing completed",
                worker_id=self.config.worker_id,
                event_id=event.event_id,
                processing_time_ms=processing_time
            )
    
    async def _process_event_with_error_handling(self, event: Event) -> WorkerResult:
        """Process event with exception handling."""
        try:
            # 1. Reconstruct state if needed
            state = await self._reconstruct_state(event)
            
            # 2. Validate event can be processed
            if not await self._can_process_event(event, state):
                logger.warning(
                    "Event cannot be processed",
                    worker_id=self.config.worker_id,
                    event_id=event.event_id
                )
                return WorkerResult(
                    success=False,
                    error_message="Event cannot be processed by this worker",
                    metadata={"validation_failed": True}
                )
            
            # 3. Process the event
            new_events = await self.process_event(event, state)
            
            # 4. Persist events
            for new_event in new_events:
                await self.event_store.append_event(new_event)
            
            # 5. Save snapshot if needed
            if state and self.config.enable_snapshots:
                await self._maybe_save_snapshot(state)
            
            # 6. Dispatch events to message bus
            await self._dispatch_events(new_events)
            
            self._processed_count += 1
            
            return WorkerResult(
                success=True,
                events_generated=new_events,
                metadata={"events_count": len(new_events)}
            )
            
        except Exception as e:
            # Handle the exception using the exception handling engine
            exception_result = await self.exception_handler.handle_exception(
                exception=e,
                context_id=event.aggregate_id,
                context_type=event.aggregate_type,
                handlers=await self._get_exception_handlers(event),
                operation_id=event.event_id
            )
            
            # Persist exception events
            for exc_event in exception_result.events_generated:
                await self.event_store.append_event(exc_event)
            
            # Dispatch exception events
            await self._dispatch_events(exception_result.events_generated)
            
            return WorkerResult(
                success=False,
                events_generated=exception_result.events_generated,
                should_retry=exception_result.should_continue,
                retry_delay_ms=exception_result.delay_ms,
                error_message=str(e),
                metadata={
                    "exception_strategy": exception_result.strategy_used.value,
                    "exception_type": type(e).__name__
                }
            )
    
    async def _reconstruct_state(self, event: Event) -> Optional[EventSourcedAggregate]:
        """Reconstruct aggregate state from events if needed."""
        if not await self._requires_state_reconstruction(event):
            return None
        
        # Get the appropriate aggregate class
        aggregate_class = await self._get_aggregate_class(event.aggregate_type)
        if not aggregate_class:
            logger.warning(
                "No aggregate class found",
                aggregate_type=event.aggregate_type,
                event_id=event.event_id
            )
            return None
        
        # Reconstruct the aggregate
        aggregate = await aggregate_class.reconstruct(event.aggregate_id, self.event_store)
        
        logger.debug(
            "State reconstructed",
            aggregate_id=event.aggregate_id,
            aggregate_type=event.aggregate_type,
            worker_id=self.config.worker_id
        )
        
        return aggregate
    
    async def _maybe_save_snapshot(self, state: EventSourcedAggregate) -> None:
        """Save a snapshot if it's time to do so."""
        if not hasattr(state, 'version') or not hasattr(state, 'to_snapshot'):
            return
        
        # Save snapshot based on frequency
        if state.version % self.config.snapshot_frequency == 0:
            snapshot_data = state.to_snapshot()
            await self.event_store.save_snapshot(
                aggregate_id=state.id,
                aggregate_type=type(state).__name__,
                state_data=snapshot_data,
                version=state.version
            )
            
            logger.debug(
                "Snapshot saved",
                aggregate_id=state.id,
                version=state.version,
                worker_id=self.config.worker_id
            )
    
    async def _dispatch_events(self, events: List[Event]) -> None:
        """Dispatch events to the message bus."""
        for event in events:
            # Publish to general event stream
            await self.message_bus.publish(f"events.{event.event_type}", event)
            
            # Add to work queue if it needs processing
            if await self._requires_processing(event):
                await self.message_bus.push_to_queue("work_queue", event.model_dump_json())
            
            logger.debug(
                "Event dispatched",
                event_id=event.event_id,
                event_type=event.event_type,
                worker_id=self.config.worker_id
            )
    
    # Abstract methods to be implemented by subclasses
    
    @abstractmethod
    async def process_event(self, event: Event, state: Optional[EventSourcedAggregate]) -> List[Event]:
        """
        Process the event and return new events to be generated.
        This is the main business logic method.
        """
        pass
    
    @abstractmethod
    async def _can_process_event(self, event: Event, state: Optional[EventSourcedAggregate]) -> bool:
        """Check if this worker can process the given event."""
        pass
    
    @abstractmethod
    async def _requires_state_reconstruction(self, event: Event) -> bool:
        """Check if state reconstruction is needed for this event."""
        pass
    
    @abstractmethod
    async def _get_aggregate_class(self, aggregate_type: str) -> Optional[Type[EventSourcedAggregate]]:
        """Get the aggregate class for the given type."""
        pass
    
    @abstractmethod
    async def _requires_processing(self, event: Event) -> bool:
        """Check if the event requires further processing by other workers."""
        pass
    
    @abstractmethod
    async def _get_exception_handlers(self, event: Event) -> List[ExceptionHandler]:
        """Get exception handlers for the given event."""
        pass
    
    # Helper methods that can be overridden by subclasses
    
    def get_supported_event_types(self) -> List[str]:
        """Get list of event types this worker can process."""
        return []
    
    def get_worker_type(self) -> str:
        """Get the type of this worker."""
        return self.__class__.__name__
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check and return status."""
        return {
            "worker_id": self.config.worker_id,
            "worker_type": self.get_worker_type(),
            "processed_count": self._processed_count,
            "status": "healthy" if not self._running else "processing",
            "supported_events": self.get_supported_event_types()
        }