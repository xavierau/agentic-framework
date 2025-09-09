"""Hybrid message bus combining SQLite persistence with Redis distribution."""

import asyncio
import json
from typing import Dict, List, Optional, Callable
from datetime import datetime, timezone
import structlog

from .base import MessageBus, Message, MessageHandler
from .redis_bus import RedisMessageBus
from ..events.event_store import EventStore, SQLiteEventStore
from ..events.event_types import Event


logger = structlog.get_logger()


class HybridMessageBus(MessageBus):
    """
    Hybrid message bus that combines SQLite for durability with Redis for distribution.
    
    Architecture:
    1. All events are first persisted to SQLite (durability)
    2. Events are then published to Redis (real-time distribution)
    3. Work queues use Redis for scalability
    4. Event replay uses SQLite for reliability
    """
    
    def __init__(
        self, 
        event_store: Optional[EventStore] = None,
        redis_bus: Optional[RedisMessageBus] = None,
        sqlite_path: str = "events.db",
        redis_url: str = "redis://localhost:6379"
    ):
        super().__init__()
        
        # Storage layer (SQLite)
        self.event_store = event_store or SQLiteEventStore(sqlite_path)
        
        # Distribution layer (Redis) 
        self.redis_bus = redis_bus or RedisMessageBus(redis_url)
        
        # Event processing configuration
        self._requires_processing_types = {
            "TaskCreated", "TaskAssigned", "WorkflowStepScheduled",
            "RetryScheduled", "CompensationTriggered"
        }
        
        # Replay state
        self._replay_active = False
        self._last_replayed_sequence = 0
    
    async def connect(self) -> None:
        """Connect to both SQLite and Redis."""
        try:
            await self.event_store.initialize()
            await self.redis_bus.connect()
            
            logger.info(
                "Hybrid message bus connected",
                sqlite_path=getattr(self.event_store, 'database_path', 'unknown'),
                redis_url=getattr(self.redis_bus, 'redis_url', 'unknown')
            )
        except Exception as e:
            logger.error("Failed to connect hybrid message bus", error=str(e))
            raise
    
    async def disconnect(self) -> None:
        """Disconnect from both layers."""
        try:
            await self.redis_bus.disconnect()
            logger.info("Hybrid message bus disconnected")
        except Exception as e:
            logger.error("Error disconnecting hybrid message bus", error=str(e))
    
    async def dispatch_event(self, event: Event) -> int:
        """
        Dispatch an event with full durability and distribution.
        
        Returns the sequence number assigned to the event.
        """
        try:
            # 1. Always persist to SQLite first (durability)
            sequence_number = await self.event_store.append_event(event)
            event.sequence_number = sequence_number
            
            logger.debug(
                "Event persisted",
                event_id=event.event_id,
                event_type=event.event_type,
                sequence_number=sequence_number
            )
            
            # 2. Publish to Redis for real-time processing
            await self._publish_to_redis(event)
            
            # 3. Add to work queue if needs processing
            if self._requires_processing(event):
                await self._add_to_work_queue(event)
            
            logger.info(
                "Event dispatched",
                event_id=event.event_id,
                event_type=event.event_type,
                sequence_number=sequence_number,
                requires_processing=self._requires_processing(event)
            )
            
            return sequence_number
            
        except Exception as e:
            logger.error(
                "Failed to dispatch event",
                event_id=event.event_id,
                event_type=event.event_type,
                error=str(e)
            )
            raise
    
    async def _publish_to_redis(self, event: Event) -> None:
        """Publish event to Redis channels."""
        try:
            # Convert Event to Message for Redis compatibility
            message = Message.create(
                sender_id="system",
                message_type=event.event_type,
                content=event.payload,
                metadata={
                    **event.metadata,
                    "event_id": event.event_id,
                    "aggregate_id": event.aggregate_id,
                    "aggregate_type": event.aggregate_type,
                    "sequence_number": event.sequence_number
                }
            )
            
            # Publish to general event stream
            await self.redis_bus.publish(f"events.{event.event_type}", message)
            
            # Publish to aggregate-specific stream
            await self.redis_bus.publish(
                f"aggregate.{event.aggregate_type}.{event.aggregate_id}", 
                message
            )
            
        except Exception as e:
            logger.error(
                "Failed to publish event to Redis",
                event_id=event.event_id,
                error=str(e)
            )
            raise
    
    async def _add_to_work_queue(self, event: Event) -> None:
        """Add event to work queue for processing."""
        try:
            # Create work item with full event data
            work_item = {
                "event_id": event.event_id,
                "event_type": event.event_type,
                "aggregate_id": event.aggregate_id,
                "aggregate_type": event.aggregate_type,
                "payload": event.payload,
                "metadata": event.metadata,
                "timestamp": event.timestamp.isoformat(),
                "sequence_number": event.sequence_number
            }
            
            await self.redis_bus.push_to_queue("work_queue", work_item)
            
            logger.debug(
                "Event added to work queue",
                event_id=event.event_id,
                event_type=event.event_type
            )
            
        except Exception as e:
            logger.error(
                "Failed to add event to work queue",
                event_id=event.event_id,
                error=str(e)
            )
            raise
    
    def _requires_processing(self, event: Event) -> bool:
        """Check if event requires processing by workers."""
        return event.event_type in self._requires_processing_types
    
    async def replay_events(
        self, 
        from_sequence: int = 0,
        to_sequence: Optional[int] = None,
        event_types: Optional[List[str]] = None
    ) -> int:
        """
        Replay events from SQLite to Redis.
        
        This is useful for:
        - Bootstrapping new workers
        - Recovering from Redis failures
        - Debugging and analysis
        
        Returns the number of events replayed.
        """
        if self._replay_active:
            logger.warning("Event replay already in progress")
            return 0
        
        self._replay_active = True
        replayed_count = 0
        
        try:
            logger.info(
                "Starting event replay",
                from_sequence=from_sequence,
                to_sequence=to_sequence,
                event_types=event_types
            )
            
            # Get events from SQLite
            events = await self.event_store.get_events_since(from_sequence)
            
            for event_record in events:
                # Filter by sequence if specified
                if to_sequence and event_record.sequence_number > to_sequence:
                    break
                
                # Filter by event type if specified
                if event_types and event_record.event_type not in event_types:
                    continue
                
                # Reconstruct Event object
                event = Event(
                    event_id=str(event_record.id),
                    event_type=event_record.event_type,
                    aggregate_id=event_record.aggregate_id,
                    aggregate_type=event_record.aggregate_type,
                    payload=event_record.payload,
                    metadata=event_record.metadata,
                    timestamp=event_record.timestamp,
                    sequence_number=event_record.sequence_number
                )
                
                # Publish to Redis (but don't persist again)
                await self._publish_to_redis(event)
                
                # Add to work queue if needed
                if self._requires_processing(event):
                    await self._add_to_work_queue(event)
                
                replayed_count += 1
                self._last_replayed_sequence = event_record.sequence_number
                
                # Small delay to avoid overwhelming Redis
                if replayed_count % 100 == 0:
                    await asyncio.sleep(0.01)
            
            logger.info(
                "Event replay completed",
                replayed_count=replayed_count,
                last_sequence=self._last_replayed_sequence
            )
            
            return replayed_count
            
        except Exception as e:
            logger.error("Event replay failed", error=str(e))
            raise
        finally:
            self._replay_active = False
    
    async def get_events_for_aggregate(
        self, 
        aggregate_id: str, 
        from_sequence: int = 0
    ) -> List[Event]:
        """Get all events for a specific aggregate from SQLite."""
        try:
            event_records = await self.event_store.get_events_for_aggregate(
                aggregate_id, from_sequence
            )
            
            events = []
            for record in event_records:
                event = Event(
                    event_id=str(record.id),
                    event_type=record.event_type,
                    aggregate_id=record.aggregate_id,
                    aggregate_type=record.aggregate_type,
                    payload=record.payload,
                    metadata=record.metadata,
                    timestamp=record.timestamp,
                    sequence_number=record.sequence_number
                )
                events.append(event)
            
            return events
            
        except Exception as e:
            logger.error(
                "Failed to get events for aggregate",
                aggregate_id=aggregate_id,
                error=str(e)
            )
            raise
    
    # MessageBus interface implementation (delegates to Redis)
    
    async def publish(self, channel: str, message: Message) -> None:
        """Publish message to Redis channel."""
        await self.redis_bus.publish(channel, message)
    
    async def subscribe(self, channel: str, handler: MessageHandler) -> None:
        """Subscribe to Redis channel."""
        await self.redis_bus.subscribe(channel, handler)
    
    async def unsubscribe(self, channel: str, handler: Optional[MessageHandler] = None) -> None:
        """Unsubscribe from Redis channel."""
        await self.redis_bus.unsubscribe(channel, handler)
    
    # Work queue interface (delegates to Redis)
    
    async def pull_work_item(self, timeout: int = 30) -> Optional[Dict]:
        """Pull work item from queue."""
        try:
            result = await self.redis_bus.pop_from_queue("work_queue", timeout)
            if result:
                # Parse work item if it's JSON
                if hasattr(result, 'to_dict'):
                    work_data = result.to_dict()
                else:
                    work_data = json.loads(result) if isinstance(result, str) else result
                
                return work_data
            return None
            
        except Exception as e:
            logger.error("Failed to pull work item", error=str(e))
            return None
    
    # Status and monitoring
    
    async def get_status(self) -> Dict[str, any]:
        """Get status of both layers."""
        try:
            next_sequence = await self.event_store.get_next_sequence_number()
            
            redis_status = "connected" if getattr(self.redis_bus, 'redis_client', None) else "disconnected"
            
            return {
                "sqlite": {
                    "database_path": getattr(self.event_store, 'database_path', 'unknown'),
                    "next_sequence": next_sequence,
                    "status": "connected"
                },
                "redis": {
                    "url": getattr(self.redis_bus, 'redis_url', 'unknown'),
                    "status": redis_status
                },
                "replay": {
                    "active": self._replay_active,
                    "last_replayed_sequence": self._last_replayed_sequence
                }
            }
            
        except Exception as e:
            logger.error("Failed to get status", error=str(e))
            return {"error": str(e)}
    
    async def get_work_queue_length(self) -> int:
        """Get the current work queue length."""
        try:
            return await self.redis_bus.get_queue_length("work_queue")
        except Exception as e:
            logger.error("Failed to get work queue length", error=str(e))
            return 0