"""Base agent class and related components."""

import asyncio
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Callable
from uuid import uuid4
import structlog

from pydantic import BaseModel, Field

from ..messaging.base import MessageBus, Message, MessageType
from .task import Task, TaskResult, TaskStatus


logger = structlog.get_logger()


class AgentStatus(str, Enum):
    """Agent status enumeration."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    BUSY = "busy"
    ERROR = "error"


class AgentCapability(BaseModel):
    """Represents an agent capability."""
    
    name: str
    description: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)
    cost: int = 1  # Relative cost of using this capability
    
    def __hash__(self):
        return hash(self.name)


TaskHandler = Callable[[Task], TaskResult]


class Agent(BaseModel):
    """Base agent class representing individual agents in the system."""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    agent_type: str
    capabilities: Set[AgentCapability] = Field(default_factory=set)
    status: AgentStatus = AgentStatus.ACTIVE
    
    # Configuration
    max_concurrent_tasks: int = 1
    heartbeat_interval: int = 30  # seconds
    
    # Runtime state
    current_tasks: Set[str] = Field(default_factory=set)
    completed_tasks: int = 0
    failed_tasks: int = 0
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_heartbeat: Optional[datetime] = None
    
    class Config:
        use_enum_values = True
        arbitrary_types_allowed = True
    
    def __init__(self, **data):
        super().__init__(**data)
        # Dependencies (will be injected) - private attributes not in Pydantic model
        self._message_bus: Optional[MessageBus] = None
        self._task_handlers: Dict[str, TaskHandler] = {}
        self._running: bool = False
    
    def set_message_bus(self, message_bus: MessageBus) -> None:
        """Set the message bus for this agent."""
        self._message_bus = message_bus
    
    def add_capability(self, capability: AgentCapability) -> None:
        """Add a capability to this agent."""
        self.capabilities.add(capability)
        logger.info(
            "Capability added",
            agent_id=self.id,
            agent_name=self.name,
            capability=capability.name
        )
    
    def remove_capability(self, capability_name: str) -> None:
        """Remove a capability from this agent."""
        self.capabilities = {c for c in self.capabilities if c.name != capability_name}
        logger.info(
            "Capability removed",
            agent_id=self.id,
            agent_name=self.name,
            capability=capability_name
        )
    
    def add_capabilities(self, capabilities: List[str]) -> 'Agent':
        """Add multiple capabilities to the agent (fluent interface)."""
        for cap_name in capabilities:
            # Verify the capability method exists in the subclass
            if not hasattr(self, cap_name):
                raise ValueError(f"Capability method '{cap_name}' not implemented in {self.__class__.__name__}")
            capability = AgentCapability(name=cap_name)
            self.add_capability(capability)
        return self
    
    def has_capability(self, capability_name: str) -> bool:
        """Check if agent has a specific capability."""
        return any(c.name == capability_name for c in self.capabilities)
    
    def has_capabilities(self, required_capabilities: List[str]) -> bool:
        """Check if agent has all required capabilities."""
        agent_capabilities = {c.name for c in self.capabilities}
        return all(cap in agent_capabilities for cap in required_capabilities)
    
    def register_task_handler(self, task_type: str, handler: TaskHandler) -> None:
        """Register a handler for a specific task type."""
        self._task_handlers[task_type] = handler
        logger.info(
            "Task handler registered",
            agent_id=self.id,
            agent_name=self.name,
            task_type=task_type
        )
    
    def can_accept_task(self, task: Task) -> bool:
        """Check if agent can accept a task."""
        return (
            self.status == AgentStatus.ACTIVE and
            len(self.current_tasks) < self.max_concurrent_tasks and
            self.has_capabilities(task.required_capabilities) and
            task.task_type in self._task_handlers
        )
    
    async def start(self) -> None:
        """Start the agent."""
        if self._running:
            return
            
        self._running = True
        self.status = AgentStatus.ACTIVE
        
        if self._message_bus:
            await self._message_bus.subscribe(f"agent.{self.id}", self._handle_message)
        
        # Start heartbeat task
        asyncio.create_task(self._heartbeat_loop())
        
        logger.info("Agent started", agent_id=self.id, agent_name=self.name)
    
    async def stop(self) -> None:
        """Stop the agent."""
        self._running = False
        self.status = AgentStatus.INACTIVE
        
        if self._message_bus:
            await self._message_bus.unsubscribe(f"agent.{self.id}")
        
        logger.info("Agent stopped", agent_id=self.id, agent_name=self.name)
    
    async def execute_task(self, task: Task) -> TaskResult:
        """Execute a task."""
        if not self.can_accept_task(task):
            return TaskResult.failure_result(f"Agent {self.id} cannot accept task {task.id}")
        
        if task.id in self.current_tasks:
            return TaskResult.failure_result(f"Task {task.id} already being executed")
        
        self.current_tasks.add(task.id)
        self.status = AgentStatus.BUSY
        
        try:
            task.start()
            
            # Send task started message
            if self._message_bus:
                message = Message.create(
                    sender_id=self.id,
                    message_type=MessageType.TASK_STARTED,
                    content={"task_id": task.id, "agent_id": self.id},
                    task_id=task.id
                )
                await self._message_bus.broadcast_task(task.id, message)
            
            # Execute the task
            handler = self._task_handlers.get(task.task_type)
            if not handler:
                raise ValueError(f"No handler for task type {task.task_type}")
            
            result = await self._execute_handler(handler, task)
            
            task.complete(result)
            self.completed_tasks += 1 if result.success else 0
            self.failed_tasks += 1 if not result.success else 0
            
            # Send completion message
            if self._message_bus:
                message_type = MessageType.TASK_COMPLETED if result.success else MessageType.TASK_FAILED
                message = Message.create(
                    sender_id=self.id,
                    message_type=message_type,
                    content={
                        "task_id": task.id,
                        "agent_id": self.id,
                        "result": result.dict()
                    },
                    task_id=task.id
                )
                await self._message_bus.broadcast_task(task.id, message)
            
            return result
            
        except Exception as e:
            error_msg = f"Error executing task {task.id}: {str(e)}"
            logger.error(error_msg, agent_id=self.id, task_id=task.id)
            
            result = TaskResult.failure_result(error_msg)
            task.complete(result)
            self.failed_tasks += 1
            
            return result
            
        finally:
            self.current_tasks.discard(task.id)
            self.status = AgentStatus.ACTIVE if len(self.current_tasks) == 0 else AgentStatus.BUSY
    
    async def process(self, task: Task, capability: str) -> None:
        """
        Process a task using a specific capability and auto-dispatch result to bus.
        The capability should be implemented as a method in the Agent subclass.
        """
        # Validate capability
        if not self.has_capability(capability):
            error_result = TaskResult.failure_result(
                f"Agent {self.id} does not have capability {capability}"
            )
            await self._dispatch_result(task, error_result, capability)
            return
        
        # Get capability method from the agent instance
        if not hasattr(self, capability):
            error_result = TaskResult.failure_result(
                f"Capability method '{capability}' not implemented"
            )
            await self._dispatch_result(task, error_result, capability)
            return
        
        capability_method = getattr(self, capability)
        
        # Execute the capability method
        try:
            task.start()
            self.current_tasks.add(task.id)
            self.status = AgentStatus.BUSY
            
            # Call the capability method with the task
            result = await self._execute_capability(capability_method, task)
            task.complete(result)
            
            # Update statistics
            if result.success:
                self.completed_tasks += 1
            else:
                self.failed_tasks += 1
            
            # Auto-dispatch to message bus
            await self._dispatch_result(task, result, capability)
            
        except Exception as e:
            error_result = TaskResult.failure_result(str(e))
            task.complete(error_result)
            self.failed_tasks += 1
            await self._dispatch_result(task, error_result, capability)
        
        finally:
            self.current_tasks.discard(task.id)
            self.status = AgentStatus.ACTIVE if len(self.current_tasks) == 0 else AgentStatus.BUSY
    
    async def _execute_capability(self, capability_method: Callable, task: Task) -> TaskResult:
        """Execute a capability method (handle both sync and async)."""
        if asyncio.iscoroutinefunction(capability_method):
            return await capability_method(task)
        else:
            # Run sync method in thread pool
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, capability_method, task)
    
    async def _dispatch_result(self, task: Task, result: TaskResult, capability: str) -> None:
        """Automatically dispatch task result to the message bus."""
        if self._message_bus:
            message_type = MessageType.TASK_COMPLETED if result.success else MessageType.TASK_FAILED
            message = Message.create(
                sender_id=self.id,
                message_type=message_type,
                content={
                    "task_id": task.id,
                    "agent_id": self.id,
                    "capability": capability,
                    "result": result.dict()
                },
                task_id=task.id
            )
            await self._message_bus.broadcast_task(task.id, message)
    
    async def _execute_handler(self, handler: TaskHandler, task: Task) -> TaskResult:
        """Execute a task handler, handling both sync and async handlers."""
        if asyncio.iscoroutinefunction(handler):
            return await handler(task)
        else:
            # Run sync handler in thread pool
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, handler, task)
    
    async def _handle_message(self, message: Message) -> None:
        """Handle incoming messages."""
        try:
            if message.message_type == MessageType.TASK_ASSIGNED:
                # Handle task assignment
                task_data = message.content.get("task")
                if task_data:
                    task = Task(**task_data)
                    await self.execute_task(task)
            
            # Add more message type handlers as needed
            
        except Exception as e:
            logger.error(
                "Error handling message",
                agent_id=self.id,
                message_id=message.id,
                error=str(e)
            )
    
    async def _heartbeat_loop(self) -> None:
        """Send periodic heartbeat messages."""
        while self._running:
            try:
                self.last_heartbeat = datetime.utcnow()
                
                if self._message_bus:
                    message = Message.create(
                        sender_id=self.id,
                        message_type=MessageType.AGENT_STATUS_UPDATE,
                        content={
                            "agent_id": self.id,
                            "status": self.status,
                            "current_tasks": list(self.current_tasks),
                            "timestamp": self.last_heartbeat.isoformat()
                        }
                    )
                    await self._message_bus.publish("system.heartbeat", message)
                
                await asyncio.sleep(self.heartbeat_interval)
                
            except Exception as e:
                logger.error("Error in heartbeat", agent_id=self.id, error=str(e))
                await asyncio.sleep(self.heartbeat_interval)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get agent statistics."""
        return {
            "id": self.id,
            "name": self.name,
            "agent_type": self.agent_type,
            "status": self.status,
            "capabilities": [c.name for c in self.capabilities],
            "current_tasks": len(self.current_tasks),
            "max_concurrent_tasks": self.max_concurrent_tasks,
            "completed_tasks": self.completed_tasks,
            "failed_tasks": self.failed_tasks,
            "success_rate": self.completed_tasks / (self.completed_tasks + self.failed_tasks) if (self.completed_tasks + self.failed_tasks) > 0 else 0,
            "created_at": self.created_at.isoformat(),
            "last_heartbeat": self.last_heartbeat.isoformat() if self.last_heartbeat else None,
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert agent to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "agent_type": self.agent_type,
            "capabilities": [c.dict() for c in self.capabilities],
            "status": self.status,
            "max_concurrent_tasks": self.max_concurrent_tasks,
            "heartbeat_interval": self.heartbeat_interval,
            "current_tasks": list(self.current_tasks),
            "completed_tasks": self.completed_tasks,
            "failed_tasks": self.failed_tasks,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "last_heartbeat": self.last_heartbeat.isoformat() if self.last_heartbeat else None,
        }