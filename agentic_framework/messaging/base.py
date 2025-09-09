"""Abstract base classes for message bus implementations."""

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Union
from uuid import uuid4


@dataclass
class Message:
    """Represents a message in the system."""
    
    id: str
    sender_id: str
    receiver_id: Optional[str]
    team_id: Optional[str]
    task_id: Optional[str]
    message_type: str
    content: Dict[str, Any]
    metadata: Dict[str, Any]
    timestamp: datetime
    
    @classmethod
    def create(
        cls,
        sender_id: str,
        message_type: str,
        content: Dict[str, Any],
        receiver_id: Optional[str] = None,
        team_id: Optional[str] = None,
        task_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "Message":
        """Create a new message."""
        return cls(
            id=str(uuid4()),
            sender_id=sender_id,
            receiver_id=receiver_id,
            team_id=team_id,
            task_id=task_id,
            message_type=message_type,
            content=content,
            metadata=metadata or {},
            timestamp=datetime.utcnow(),
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary."""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Message":
        """Create message from dictionary."""
        data = data.copy()
        data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        return cls(**data)
    
    def to_json(self) -> str:
        """Convert message to JSON string."""
        return json.dumps(self.to_dict())
    
    @classmethod
    def from_json(cls, json_str: str) -> "Message":
        """Create message from JSON string."""
        return cls.from_dict(json.loads(json_str))


MessageHandler = Callable[[Message], None]


class MessageBus(ABC):
    """Abstract base class for message bus implementations."""
    
    def __init__(self):
        self._handlers: Dict[str, List[MessageHandler]] = {}
    
    @abstractmethod
    async def connect(self) -> None:
        """Connect to the message bus."""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from the message bus."""
        pass
    
    @abstractmethod
    async def publish(self, channel: str, message: Message) -> None:
        """Publish a message to a channel."""
        pass
    
    @abstractmethod
    async def subscribe(self, channel: str, handler: MessageHandler) -> None:
        """Subscribe to messages on a channel."""
        pass
    
    @abstractmethod
    async def unsubscribe(self, channel: str, handler: Optional[MessageHandler] = None) -> None:
        """Unsubscribe from a channel."""
        pass
    
    async def send_to_agent(self, agent_id: str, message: Message) -> None:
        """Send a message directly to an agent."""
        await self.publish(f"agent.{agent_id}", message)
    
    async def send_to_team(self, team_id: str, message: Message) -> None:
        """Send a message to all team members."""
        await self.publish(f"team.{team_id}", message)
    
    async def broadcast_task(self, task_id: str, message: Message) -> None:
        """Broadcast a task-related message."""
        await self.publish(f"task.{task_id}", message)
    
    def add_handler(self, message_type: str, handler: MessageHandler) -> None:
        """Add a message handler for a specific message type."""
        if message_type not in self._handlers:
            self._handlers[message_type] = []
        self._handlers[message_type].append(handler)
    
    def remove_handler(self, message_type: str, handler: MessageHandler) -> None:
        """Remove a message handler."""
        if message_type in self._handlers:
            try:
                self._handlers[message_type].remove(handler)
            except ValueError:
                pass
    
    async def handle_message(self, message: Message) -> None:
        """Handle an incoming message by calling registered handlers."""
        import asyncio
        handlers = self._handlers.get(message.message_type, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(message)
                else:
                    handler(message)
            except Exception as e:
                # Log error but don't stop processing other handlers
                import structlog
                logger = structlog.get_logger()
                logger.error("Error handling message", message_id=message.id, error=str(e))


# Message type constants
class MessageType:
    """Standard message types used in the framework."""
    
    # Task-related messages
    TASK_ASSIGNED = "task.assigned"
    TASK_STARTED = "task.started"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"
    
    # Agent-related messages
    AGENT_STATUS_UPDATE = "agent.status_update"
    AGENT_CAPABILITY_UPDATE = "agent.capability_update"
    
    # Team-related messages
    TEAM_MEMBER_ADDED = "team.member_added"
    TEAM_MEMBER_REMOVED = "team.member_removed"
    TEAM_TASK_REQUEST = "team.task_request"
    TEAM_TASK_RESPONSE = "team.task_response"
    
    # Orchestration messages
    PLAN_CREATED = "orchestration.plan_created"
    PLAN_UPDATED = "orchestration.plan_updated"
    WORK_ASSIGNED = "orchestration.work_assigned"
    PROGRESS_UPDATE = "orchestration.progress_update"