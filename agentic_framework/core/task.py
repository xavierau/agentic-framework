"""Task management classes."""

import asyncio
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
from uuid import uuid4
import structlog

from pydantic import BaseModel, Field


logger = structlog.get_logger()


class TaskStatus(str, Enum):
    """Task status enumeration."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(int, Enum):
    """Task priority levels."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


class TaskResult(BaseModel):
    """Represents the result of a task execution."""
    
    success: bool
    data: Dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    @classmethod
    def success_result(cls, data: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None) -> "TaskResult":
        """Create a successful task result."""
        return cls(
            success=True,
            data=data,
            metadata=metadata or {}
        )
    
    @classmethod
    def failure_result(cls, error_message: str, metadata: Optional[Dict[str, Any]] = None) -> "TaskResult":
        """Create a failed task result."""
        return cls(
            success=False,
            error_message=error_message,
            metadata=metadata or {}
        )


TaskExecutor = Callable[["Task"], TaskResult]


class Task(BaseModel):
    """Represents a task in the system."""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    title: str
    description: Optional[str] = None
    task_type: str = "general"
    priority: TaskPriority = TaskPriority.NORMAL
    
    # Task hierarchy
    parent_task_id: Optional[str] = None
    subtask_ids: List[str] = Field(default_factory=list)
    
    # Assignment
    assigned_team_id: Optional[str] = None
    assigned_agent_id: Optional[str] = None
    
    # Status and lifecycle
    status: TaskStatus = TaskStatus.PENDING
    input_data: Dict[str, Any] = Field(default_factory=dict)
    result: Optional[TaskResult] = None
    
    # Requirements and constraints
    required_capabilities: List[str] = Field(default_factory=list)
    dependencies: List[str] = Field(default_factory=list)
    estimated_duration: Optional[int] = None  # in seconds
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    deadline: Optional[datetime] = None
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        use_enum_values = True
    
    @classmethod
    def create(cls, title: str, task_type: str = "general") -> "TaskBuilder":
        """Create a task builder for fluent task creation."""
        return TaskBuilder(title, task_type)
    
    def __init__(self, title: str = None, task_type: str = "general", **kwargs):
        """Initialize task with optional convenience parameters."""
        if title:
            kwargs["title"] = title
        if "task_type" not in kwargs:
            kwargs["task_type"] = task_type
        super().__init__(**kwargs)
    
    def start(self) -> None:
        """Mark task as started."""
        if self.status != TaskStatus.PENDING:
            raise ValueError(f"Cannot start task in status {self.status}")
        
        self.status = TaskStatus.IN_PROGRESS
        self.started_at = datetime.utcnow()
        
        logger.info("Task started", task_id=self.id, title=self.title)
    
    def complete(self, result: TaskResult) -> None:
        """Mark task as completed with result."""
        if self.status != TaskStatus.IN_PROGRESS:
            raise ValueError(f"Cannot complete task in status {self.status}")
        
        self.status = TaskStatus.COMPLETED if result.success else TaskStatus.FAILED
        self.result = result
        self.completed_at = datetime.utcnow()
        
        logger.info(
            "Task completed",
            task_id=self.id,
            title=self.title,
            success=result.success
        )
    
    def cancel(self, reason: Optional[str] = None) -> None:
        """Cancel the task."""
        if self.status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
            raise ValueError(f"Cannot cancel task in status {self.status}")
        
        self.status = TaskStatus.CANCELLED
        self.completed_at = datetime.utcnow()
        
        if reason:
            self.metadata["cancellation_reason"] = reason
            
        logger.info("Task cancelled", task_id=self.id, title=self.title, reason=reason)
    
    def add_subtask(self, subtask: "Task") -> None:
        """Add a subtask."""
        subtask.parent_task_id = self.id
        if subtask.id not in self.subtask_ids:
            self.subtask_ids.append(subtask.id)
    
    def is_ready_to_start(self, completed_dependencies: set[str]) -> bool:
        """Check if task is ready to start based on dependencies."""
        return (
            self.status == TaskStatus.PENDING and
            all(dep_id in completed_dependencies for dep_id in self.dependencies)
        )
    
    def is_overdue(self) -> bool:
        """Check if task is overdue."""
        if not self.deadline:
            return False
        return datetime.utcnow() > self.deadline and self.status not in [
            TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED
        ]
    
    def get_duration(self) -> Optional[int]:
        """Get task duration in seconds if completed."""
        if self.started_at and self.completed_at:
            return int((self.completed_at - self.started_at).total_seconds())
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert task to dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "task_type": self.task_type,
            "priority": self.priority,
            "parent_task_id": self.parent_task_id,
            "subtask_ids": self.subtask_ids,
            "assigned_team_id": self.assigned_team_id,
            "assigned_agent_id": self.assigned_agent_id,
            "status": self.status,
            "input_data": self.input_data,
            "result": self.result.dict() if self.result else None,
            "required_capabilities": self.required_capabilities,
            "dependencies": self.dependencies,
            "estimated_duration": self.estimated_duration,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "metadata": self.metadata,
        }


class TaskBuilder:
    """Builder class for creating tasks."""
    
    def __init__(self, title: str, task_type: str):
        self._task = Task(title=title, task_type=task_type)
    
    def description(self, description: str) -> "TaskBuilder":
        """Set task description."""
        self._task.description = description
        return self
    
    def priority(self, priority: TaskPriority) -> "TaskBuilder":
        """Set task priority."""
        self._task.priority = priority
        return self
    
    def input_data(self, data: Dict[str, Any]) -> "TaskBuilder":
        """Set task input data."""
        self._task.input_data = data
        return self
    
    def required_capabilities(self, capabilities: List[str]) -> "TaskBuilder":
        """Set required capabilities."""
        self._task.required_capabilities = capabilities
        return self
    
    def requires(self, *capabilities: str) -> "TaskBuilder":
        """Set required capabilities (alternative method name)."""
        self._task.required_capabilities = list(capabilities)
        return self
    
    def of_type(self, task_type: str) -> "TaskBuilder":
        """Set task type (alternative method name)."""
        self._task.task_type = task_type
        return self
    
    def with_data(self, **data) -> "TaskBuilder":
        """Set input data using keyword arguments."""
        self._task.input_data.update(data)
        return self
    
    def dependencies(self, dependencies: List[str]) -> "TaskBuilder":
        """Set task dependencies."""
        self._task.dependencies = dependencies
        return self
    
    def estimated_duration(self, seconds: int) -> "TaskBuilder":
        """Set estimated duration in seconds."""
        self._task.estimated_duration = seconds
        return self
    
    def deadline(self, deadline: datetime) -> "TaskBuilder":
        """Set task deadline."""
        self._task.deadline = deadline
        return self
    
    def metadata(self, **kwargs) -> "TaskBuilder":
        """Add metadata to the task."""
        self._task.metadata.update(kwargs)
        return self
    
    def build(self) -> Task:
        """Build and return the task."""
        return self._task