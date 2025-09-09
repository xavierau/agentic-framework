"""Redis-based message bus implementation."""

import asyncio
import json
from typing import Dict, List, Optional
import redis.asyncio as redis
import structlog

from .base import MessageBus, Message, MessageHandler


logger = structlog.get_logger()


class RedisMessageBus(MessageBus):
    """Redis-based message bus implementation."""
    
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        super().__init__()
        self.redis_url = redis_url
        self.redis_client: Optional[redis.Redis] = None
        self.pubsub: Optional[redis.client.PubSub] = None
        self._subscriptions: Dict[str, List[MessageHandler]] = {}
        self._listen_task: Optional[asyncio.Task] = None
        
    async def connect(self) -> None:
        """Connect to Redis."""
        try:
            self.redis_client = redis.from_url(self.redis_url)
            self.pubsub = self.redis_client.pubsub()
            await self.redis_client.ping()
            logger.info("Connected to Redis", redis_url=self.redis_url)
        except Exception as e:
            logger.error("Failed to connect to Redis", error=str(e))
            raise
    
    async def disconnect(self) -> None:
        """Disconnect from Redis."""
        if self._listen_task:
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass
        
        if self.pubsub:
            await self.pubsub.aclose()
            
        if self.redis_client:
            await self.redis_client.aclose()
            
        logger.info("Disconnected from Redis")
    
    async def publish(self, channel: str, message: Message) -> None:
        """Publish a message to a Redis channel."""
        if not self.redis_client:
            raise RuntimeError("Not connected to Redis")
            
        message_json = message.to_json()
        await self.redis_client.publish(channel, message_json)
        
        logger.debug(
            "Published message",
            channel=channel,
            message_id=message.id,
            message_type=message.message_type
        )
    
    async def subscribe(self, channel: str, handler: MessageHandler) -> None:
        """Subscribe to messages on a Redis channel."""
        if not self.pubsub:
            raise RuntimeError("Not connected to Redis")
            
        # Add handler to our internal tracking
        if channel not in self._subscriptions:
            self._subscriptions[channel] = []
            # Subscribe to the channel in Redis
            await self.pubsub.subscribe(channel)
            logger.info("Subscribed to channel", channel=channel)
        
        self._subscriptions[channel].append(handler)
        
        # Start listening if not already started
        if not self._listen_task or self._listen_task.done():
            self._listen_task = asyncio.create_task(self._listen_for_messages())
    
    async def unsubscribe(self, channel: str, handler: Optional[MessageHandler] = None) -> None:
        """Unsubscribe from a Redis channel."""
        if channel not in self._subscriptions:
            return
            
        if handler:
            # Remove specific handler
            try:
                self._subscriptions[channel].remove(handler)
            except ValueError:
                pass
        else:
            # Remove all handlers
            self._subscriptions[channel] = []
        
        # If no handlers left, unsubscribe from Redis
        if not self._subscriptions[channel]:
            if self.pubsub:
                await self.pubsub.unsubscribe(channel)
            del self._subscriptions[channel]
            logger.info("Unsubscribed from channel", channel=channel)
    
    async def _listen_for_messages(self) -> None:
        """Listen for messages from Redis and dispatch to handlers."""
        if not self.pubsub:
            return
            
        logger.info("Started listening for messages")
        
        try:
            async for redis_message in self.pubsub.listen():
                if redis_message['type'] == 'message':
                    try:
                        # Parse the message
                        message_data = redis_message['data']
                        if isinstance(message_data, bytes):
                            message_data = message_data.decode('utf-8')
                        
                        message = Message.from_json(message_data)
                        channel = redis_message['channel']
                        if isinstance(channel, bytes):
                            channel = channel.decode('utf-8')
                        
                        # Dispatch to handlers
                        await self._dispatch_message(channel, message)
                        
                    except Exception as e:
                        logger.error("Error processing message", error=str(e))
                        
        except asyncio.CancelledError:
            logger.info("Message listening cancelled")
        except Exception as e:
            logger.error("Error in message listener", error=str(e))
    
    async def _dispatch_message(self, channel: str, message: Message) -> None:
        """Dispatch a message to registered handlers."""
        # Dispatch to channel-specific handlers
        handlers = self._subscriptions.get(channel, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(message)
                else:
                    handler(message)
            except Exception as e:
                logger.error(
                    "Error in message handler",
                    channel=channel,
                    message_id=message.id,
                    error=str(e)
                )
        
        # Also dispatch to general message type handlers
        await self.handle_message(message)
    
    async def get_queue_length(self, channel: str) -> int:
        """Get the number of messages in a channel (for list-based channels)."""
        if not self.redis_client:
            raise RuntimeError("Not connected to Redis")
        return await self.redis_client.llen(channel)
    
    async def push_to_queue(self, queue_name: str, message: Message) -> None:
        """Push a message to a Redis list (queue)."""
        if not self.redis_client:
            raise RuntimeError("Not connected to Redis")
        await self.redis_client.rpush(queue_name, message.to_json())
    
    async def pop_from_queue(self, queue_name: str, timeout: int = 0) -> Optional[Message]:
        """Pop a message from a Redis list (queue)."""
        if not self.redis_client:
            raise RuntimeError("Not connected to Redis")
            
        result = await self.redis_client.blpop(queue_name, timeout=timeout)
        if result:
            _, message_json = result
            if isinstance(message_json, bytes):
                message_json = message_json.decode('utf-8')
            return Message.from_json(message_json)
        return None