"""Event types and domain events for the agentic framework."""

from abc import ABC
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from uuid import uuid4
from pydantic import BaseModel, Field


class Event(BaseModel, ABC):
    """Base class for all events in the system."""
    
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    event_type: str
    aggregate_id: str
    aggregate_type: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    sequence_number: Optional[int] = None  # Set by event store
    
    def __init__(self, **data):
        # Auto-set event_type from class name if not provided
        if 'event_type' not in data:
            data['event_type'] = self.__class__.__name__
        super().__init__(**data)


# Agent Events
class AgentCreated(Event):
    """Fired when a new agent is created."""
    
    def __init__(self, agent_id: str, name: str, agent_type: str, capabilities: List[str], **kwargs):
        super().__init__(
            aggregate_id=agent_id,
            aggregate_type="Agent",
            payload={
                "name": name,
                "agent_type": agent_type,
                "capabilities": capabilities
            },
            **kwargs
        )


class AgentCapabilityAdded(Event):
    """Fired when a capability is added to an agent."""
    
    def __init__(self, agent_id: str, capability: str, **kwargs):
        super().__init__(
            aggregate_id=agent_id,
            aggregate_type="Agent",
            payload={"capability": capability},
            **kwargs
        )


class AgentStatusChanged(Event):
    """Fired when an agent's status changes."""
    
    def __init__(self, agent_id: str, old_status: str, new_status: str, **kwargs):
        super().__init__(
            aggregate_id=agent_id,
            aggregate_type="Agent",
            payload={
                "old_status": old_status,
                "new_status": new_status
            },
            **kwargs
        )


# Team Events  
class TeamCreated(Event):
    """Fired when a new team is created."""
    
    def __init__(self, team_id: str, name: str, description: Optional[str] = None, **kwargs):
        super().__init__(
            aggregate_id=team_id,
            aggregate_type="Team",
            payload={
                "name": name,
                "description": description
            },
            **kwargs
        )


class TeamMemberAdded(Event):
    """Fired when an agent is added to a team."""
    
    def __init__(self, team_id: str, agent_id: str, role: str = "member", **kwargs):
        super().__init__(
            aggregate_id=team_id,
            aggregate_type="Team", 
            payload={
                "agent_id": agent_id,
                "role": role
            },
            **kwargs
        )


class TeamLeadAssigned(Event):
    """Fired when a lead is assigned to a team."""
    
    def __init__(self, team_id: str, lead_agent_id: str, **kwargs):
        super().__init__(
            aggregate_id=team_id,
            aggregate_type="Team",
            payload={"lead_agent_id": lead_agent_id},
            **kwargs
        )


# Task Events
class TaskCreated(Event):
    """Fired when a new task is created."""
    
    def __init__(
        self, 
        task_id: str, 
        title: str, 
        task_type: str,
        priority: int = 2,
        required_capabilities: Optional[List[str]] = None,
        input_data: Optional[Dict[str, Any]] = None,
        workflow_id: Optional[str] = None,
        **kwargs
    ):
        super().__init__(
            aggregate_id=task_id,
            aggregate_type="Task",
            payload={
                "title": title,
                "task_type": task_type,
                "priority": priority,
                "required_capabilities": required_capabilities or [],
                "input_data": input_data or {},
                "workflow_id": workflow_id
            },
            **kwargs
        )


class TaskAssigned(Event):
    """Fired when a task is assigned to an agent or team."""
    
    def __init__(
        self, 
        task_id: str, 
        assignee_id: str, 
        assignee_type: str,  # "Agent" or "Team"
        **kwargs
    ):
        super().__init__(
            aggregate_id=task_id,
            aggregate_type="Task",
            payload={
                "assignee_id": assignee_id,
                "assignee_type": assignee_type
            },
            **kwargs
        )


class TaskStarted(Event):
    """Fired when task execution begins."""
    
    def __init__(self, task_id: str, executor_id: str, **kwargs):
        super().__init__(
            aggregate_id=task_id,
            aggregate_type="Task", 
            payload={"executor_id": executor_id},
            **kwargs
        )


class TaskCompleted(Event):
    """Fired when a task is completed successfully."""
    
    def __init__(
        self, 
        task_id: str, 
        result: Dict[str, Any], 
        executor_id: str,
        **kwargs
    ):
        super().__init__(
            aggregate_id=task_id,
            aggregate_type="Task",
            payload={
                "result": result,
                "executor_id": executor_id
            },
            **kwargs
        )


class TaskFailed(Event):
    """Fired when a task fails."""
    
    def __init__(
        self, 
        task_id: str, 
        error_message: str, 
        executor_id: str,
        retry_count: int = 0,
        **kwargs
    ):
        super().__init__(
            aggregate_id=task_id,
            aggregate_type="Task",
            payload={
                "error_message": error_message,
                "executor_id": executor_id,
                "retry_count": retry_count
            },
            **kwargs
        )


class TaskCancelled(Event):
    """Fired when a task is cancelled."""
    
    def __init__(self, task_id: str, reason: str, cancelled_by: str, **kwargs):
        super().__init__(
            aggregate_id=task_id,
            aggregate_type="Task",
            payload={
                "reason": reason,
                "cancelled_by": cancelled_by
            },
            **kwargs
        )


# Workflow Events
class WorkflowDefined(Event):
    """Fired when a new workflow is defined."""
    
    def __init__(
        self, 
        workflow_id: str, 
        name: str, 
        definition: Dict[str, Any],
        version: int = 1,
        **kwargs
    ):
        super().__init__(
            aggregate_id=workflow_id,
            aggregate_type="Workflow",
            payload={
                "name": name,
                "definition": definition,
                "version": version
            },
            **kwargs
        )


class WorkflowExecutionStarted(Event):
    """Fired when workflow execution begins."""
    
    def __init__(self, execution_id: str, workflow_id: str, task_id: str, **kwargs):
        super().__init__(
            aggregate_id=execution_id,
            aggregate_type="WorkflowExecution",
            payload={
                "workflow_id": workflow_id,
                "task_id": task_id
            },
            **kwargs
        )


class WorkflowStepScheduled(Event):
    """Fired when a workflow step is scheduled for execution."""
    
    def __init__(
        self, 
        execution_id: str, 
        step_id: str, 
        step_type: str,
        step_data: Dict[str, Any],
        dependencies: Optional[List[str]] = None,
        **kwargs
    ):
        super().__init__(
            aggregate_id=execution_id,
            aggregate_type="WorkflowExecution",
            payload={
                "step_id": step_id,
                "step_type": step_type,
                "step_data": step_data,
                "dependencies": dependencies or []
            },
            **kwargs
        )


class WorkflowStepCompleted(Event):
    """Fired when a workflow step completes successfully."""
    
    def __init__(
        self, 
        execution_id: str, 
        step_id: str, 
        result: Dict[str, Any],
        next_step: Optional[str] = None,
        **kwargs
    ):
        super().__init__(
            aggregate_id=execution_id,
            aggregate_type="WorkflowExecution",
            payload={
                "step_id": step_id,
                "result": result,
                "next_step": next_step
            },
            **kwargs
        )


class WorkflowStepFailed(Event):
    """Fired when a workflow step fails."""
    
    def __init__(
        self, 
        execution_id: str, 
        step_id: str, 
        error_message: str,
        retry_count: int = 0,
        **kwargs
    ):
        super().__init__(
            aggregate_id=execution_id,
            aggregate_type="WorkflowExecution",
            payload={
                "step_id": step_id,
                "error_message": error_message,
                "retry_count": retry_count
            },
            **kwargs
        )


# Exception Handling Events
class ExceptionOccurred(Event):
    """Fired when an exception occurs during processing."""
    
    def __init__(
        self, 
        context_id: str,  # Could be task_id, execution_id, etc.
        context_type: str,
        exception_type: str,
        error_message: str,
        stack_trace: Optional[str] = None,
        **kwargs
    ):
        super().__init__(
            aggregate_id=context_id,
            aggregate_type=context_type,
            payload={
                "exception_type": exception_type,
                "error_message": error_message,
                "stack_trace": stack_trace
            },
            **kwargs
        )


class RetryScheduled(Event):
    """Fired when a retry is scheduled for a failed operation."""
    
    def __init__(
        self, 
        context_id: str,
        context_type: str,
        operation_id: str,
        attempt_number: int,
        delay_ms: int,
        **kwargs
    ):
        super().__init__(
            aggregate_id=context_id,
            aggregate_type=context_type,
            payload={
                "operation_id": operation_id,
                "attempt_number": attempt_number,
                "delay_ms": delay_ms
            },
            **kwargs
        )


class CompensationTriggered(Event):
    """Fired when compensation actions are triggered (Saga pattern)."""
    
    def __init__(
        self, 
        context_id: str,
        context_type: str,
        failed_step_id: str,
        compensation_steps: List[str],
        **kwargs
    ):
        super().__init__(
            aggregate_id=context_id,
            aggregate_type=context_type,
            payload={
                "failed_step_id": failed_step_id,
                "compensation_steps": compensation_steps
            },
            **kwargs
        )


# Plan Events
class PlanCreated(Event):
    """Fired when an execution plan is created."""
    
    def __init__(
        self, 
        plan_id: str, 
        root_task_id: str, 
        tasks: List[Dict[str, Any]],
        dependencies: Dict[str, List[str]],
        **kwargs
    ):
        super().__init__(
            aggregate_id=plan_id,
            aggregate_type="ExecutionPlan",
            payload={
                "root_task_id": root_task_id,
                "tasks": tasks,
                "dependencies": dependencies
            },
            **kwargs
        )


class PlanExecutionStarted(Event):
    """Fired when plan execution begins."""
    
    def __init__(self, plan_id: str, **kwargs):
        super().__init__(
            aggregate_id=plan_id,
            aggregate_type="ExecutionPlan",
            **kwargs
        )


class PlanCompleted(Event):
    """Fired when a plan execution completes."""
    
    def __init__(
        self, 
        plan_id: str, 
        success: bool, 
        stats: Dict[str, int],
        **kwargs
    ):
        super().__init__(
            aggregate_id=plan_id,
            aggregate_type="ExecutionPlan",
            payload={
                "success": success,
                "stats": stats
            },
            **kwargs
        )


# Event Type Registry
class EventType:
    """Registry of event type constants."""
    
    # Agent events
    AGENT_CREATED = "AgentCreated"
    AGENT_CAPABILITY_ADDED = "AgentCapabilityAdded"
    AGENT_STATUS_CHANGED = "AgentStatusChanged"
    
    # Team events
    TEAM_CREATED = "TeamCreated"
    TEAM_MEMBER_ADDED = "TeamMemberAdded"
    TEAM_LEAD_ASSIGNED = "TeamLeadAssigned"
    
    # Task events
    TASK_CREATED = "TaskCreated"
    TASK_ASSIGNED = "TaskAssigned"
    TASK_STARTED = "TaskStarted"
    TASK_COMPLETED = "TaskCompleted"
    TASK_FAILED = "TaskFailed"
    TASK_CANCELLED = "TaskCancelled"
    
    # Workflow events
    WORKFLOW_DEFINED = "WorkflowDefined"
    WORKFLOW_EXECUTION_STARTED = "WorkflowExecutionStarted"
    WORKFLOW_STEP_SCHEDULED = "WorkflowStepScheduled"
    WORKFLOW_STEP_COMPLETED = "WorkflowStepCompleted"
    WORKFLOW_STEP_FAILED = "WorkflowStepFailed"
    
    # Exception handling events
    EXCEPTION_OCCURRED = "ExceptionOccurred"
    RETRY_SCHEDULED = "RetryScheduled"
    COMPENSATION_TRIGGERED = "CompensationTriggered"
    
    # Plan events
    PLAN_CREATED = "PlanCreated"
    PLAN_EXECUTION_STARTED = "PlanExecutionStarted"
    PLAN_COMPLETED = "PlanCompleted"