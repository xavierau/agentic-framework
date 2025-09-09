"""In-memory message bus implementation for local development and testing."""

import asyncio
from collections import defaultdict
from typing import Dict, List, Optional, Set
import structlog

from .base import MessageBus, Message, MessageHandler


logger = structlog.get_logger()


class InMemoryMessageBus(MessageBus):
    """
    In-memory message bus implementation.
    
    This provides a fully functional message bus that runs entirely in memory
    without requiring external services like Redis. Perfect for development,
    testing, and single-process deployments.
    
    Features:
    - Full pub/sub messaging
    - Channel subscriptions 
    - Message queuing
    - Async message handling
    - No external dependencies
    """
    
    def __init__(self):
        super().__init__()
        self._channels: Dict[str, List[MessageHandler]] = defaultdict(list)
        self._message_queue: asyncio.Queue = asyncio.Queue()
        self._connected = False
        self._processor_task: Optional[asyncio.Task] = None
        self._subscriber_tasks: Set[asyncio.Task] = set()
        
    async def connect(self) -> None:
        """Initialize the in-memory message bus."""
        if self._connected:
            logger.warning("Already connected to in-memory message bus")
            return
            
        self._message_queue = asyncio.Queue()
        self._connected = True
        
        # Start the message processor task
        self._processor_task = asyncio.create_task(self._process_messages())
        
        logger.info("Connected to in-memory message bus")
    
    async def disconnect(self) -> None:
        """Disconnect and cleanup resources."""
        if not self._connected:
            return
            
        self._connected = False
        
        # Cancel the processor task
        if self._processor_task:
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass
        
        # Cancel all subscriber tasks
        for task in list(self._subscriber_tasks):
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        # Clear all data
        self._channels.clear()
        self._subscriber_tasks.clear()
        
        # Drain the queue
        while not self._message_queue.empty():
            try:
                self._message_queue.get_nowait()
                self._message_queue.task_done()
            except asyncio.QueueEmpty:
                break
        
        logger.info("Disconnected from in-memory message bus")
    
    async def publish(self, channel: str, message: Message) -> None:
        """Publish a message to a channel."""
        if not self._connected:
            logger.error("Cannot publish - not connected to message bus")
            return
        
        logger.debug("Publishing message", channel=channel, message_id=message.id, message_type=message.message_type)
        
        # Add to queue for processing
        await self._message_queue.put((channel, message))
    
    async def subscribe(self, channel: str, handler: MessageHandler) -> None:
        """Subscribe to messages on a channel."""
        if not self._connected:
            logger.error("Cannot subscribe - not connected to message bus")
            return
        
        logger.debug("Subscribing to channel", channel=channel)
        self._channels[channel].append(handler)
    
    async def unsubscribe(self, channel: str, handler: Optional[MessageHandler] = None) -> None:
        """Unsubscribe from a channel."""
        if channel not in self._channels:
            return
        
        if handler is None:
            # Unsubscribe all handlers for this channel
            logger.debug("Unsubscribing all handlers from channel", channel=channel)
            self._channels[channel].clear()
        else:
            # Unsubscribe specific handler
            try:
                self._channels[channel].remove(handler)
                logger.debug("Unsubscribed handler from channel", channel=channel)
            except ValueError:
                logger.warning("Handler not found for unsubscribe", channel=channel)
    
    async def _process_messages(self) -> None:
        """Background task to process messages from the queue."""
        logger.debug("Started message processor task")
        
        try:
            while self._connected:
                try:
                    # Wait for a message with timeout to allow clean shutdown
                    channel, message = await asyncio.wait_for(
                        self._message_queue.get(),
                        timeout=0.1
                    )
                    
                    # Process the message
                    await self._dispatch_message(channel, message)
                    
                    # Mark task as done
                    self._message_queue.task_done()
                    
                except asyncio.TimeoutError:
                    # Timeout is expected - allows us to check _connected status
                    continue
                    
        except asyncio.CancelledError:
            logger.debug("Message processor task cancelled")
            raise
        except Exception as e:
            logger.error("Error in message processor", error=str(e))
        finally:
            logger.debug("Message processor task finished")
    
    async def _dispatch_message(self, channel: str, message: Message) -> None:
        """Dispatch a message to all subscribers of a channel."""
        handlers = self._channels.get(channel, [])
        
        if not handlers:
            logger.debug("No handlers for channel", channel=channel, message_id=message.id)
            return
        
        logger.debug(
            "Dispatching message to handlers", 
            channel=channel, 
            message_id=message.id, 
            handler_count=len(handlers)
        )
        
        # Create tasks for all handlers to run concurrently
        tasks = []
        for handler in handlers:
            task = asyncio.create_task(self._call_handler(handler, message))
            tasks.append(task)
            self._subscriber_tasks.add(task)
        
        # Wait for all handlers to complete
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Clean up completed tasks
            for task in tasks:
                self._subscriber_tasks.discard(task)
            
            # Log any errors
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(
                        "Handler error", 
                        channel=channel, 
                        message_id=message.id, 
                        handler_index=i,
                        error=str(result)
                    )
    
    async def _call_handler(self, handler: MessageHandler, message: Message) -> None:
        """Safely call a message handler."""
        try:
            if asyncio.iscoroutinefunction(handler):
                await handler(message)
            else:
                # Run sync handler in thread pool to avoid blocking
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, handler, message)
        except Exception as e:
            logger.error("Error calling message handler", message_id=message.id, error=str(e))
            raise
    
    def get_stats(self) -> Dict[str, any]:
        """Get statistics about the message bus."""
        return {
            "connected": self._connected,
            "channels": len(self._channels),
            "total_handlers": sum(len(handlers) for handlers in self._channels.values()),
            "queue_size": self._message_queue.qsize(),
            "active_subscriber_tasks": len(self._subscriber_tasks),
            "channel_details": {
                channel: len(handlers) 
                for channel, handlers in self._channels.items() 
                if handlers
            }
        }
    
    def is_connected(self) -> bool:
        """Check if the message bus is connected."""
        return self._connected
    
    async def wait_for_empty_queue(self, timeout: float = 5.0) -> bool:
        """Wait for the message queue to be empty (useful for testing)."""
        try:
            await asyncio.wait_for(self._message_queue.join(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False