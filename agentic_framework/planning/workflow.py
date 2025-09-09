"""Workflow definition and storage for deterministic planning."""

import json
import sqlite3
from typing import Dict, List, Optional, Union, Literal, Any
from datetime import datetime, timezone
from uuid import uuid4
from pydantic import BaseModel, Field
import structlog


logger = structlog.get_logger()


class TaskSpec(BaseModel):
    """Specification for a task within a workflow step."""
    
    task_type: str
    required_capabilities: List[str]
    input_mapping: Dict[str, str] = Field(default_factory=dict)  # Map workflow data to task input
    output_mapping: Dict[str, str] = Field(default_factory=dict)  # Map task output to workflow data
    timeout_ms: Optional[int] = None


class ParallelSpec(BaseModel):
    """Specification for parallel execution of multiple steps."""
    
    steps: List[str]  # List of step IDs to execute in parallel
    wait_for_all: bool = True  # If False, proceed when first completes
    timeout_ms: Optional[int] = None


class ConditionalSpec(BaseModel):
    """Specification for conditional execution."""
    
    condition: str  # JSONPath or simple expression to evaluate
    true_step: Optional[str] = None  # Step to execute if condition is true
    false_step: Optional[str] = None  # Step to execute if condition is false


class LoopSpec(BaseModel):
    """Specification for loop execution."""
    
    loop_type: Literal["while", "for", "foreach"]
    condition: Optional[str] = None  # For while loops
    iterations: Optional[int] = None  # For for loops
    collection_path: Optional[str] = None  # JSONPath for foreach loops
    body_step: str  # Step ID to execute in loop body


class RetryPolicy(BaseModel):
    """Configuration for retry behavior."""
    
    max_attempts: int = 3
    backoff_strategy: Literal["exponential", "linear", "fixed"] = "exponential"
    initial_delay_ms: int = 1000
    max_delay_ms: int = 60000
    multiplier: float = 2.0
    jitter: bool = True


class ExceptionHandler(BaseModel):
    """Configuration for exception handling."""
    
    exception_types: List[str] = Field(default_factory=lambda: ["*"])  # * means all exceptions
    strategy: Literal["retry", "compensate", "escalate", "fail"] = "retry"
    retry_policy: Optional[RetryPolicy] = None
    compensation_steps: Optional[List[str]] = None
    escalation_target: Optional[str] = None
    max_escalations: int = 3


class CompensationAction(BaseModel):
    """Specification for compensation actions (Saga pattern)."""
    
    step_id: str
    compensation_task: TaskSpec
    timeout_ms: int = 30000
    ignore_failures: bool = True  # Continue compensation even if this step fails


class WorkflowStep(BaseModel):
    """Defines a single step in a workflow."""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    type: Literal["task", "parallel", "conditional", "loop"] = "task"
    
    # Step specifications (only one should be set based on type)
    task_spec: Optional[TaskSpec] = None
    parallel_spec: Optional[ParallelSpec] = None
    conditional_spec: Optional[ConditionalSpec] = None
    loop_spec: Optional[LoopSpec] = None
    
    # Flow control
    on_success: Optional[str] = None  # Next step ID on success
    on_failure: Optional[str] = None  # Step ID on failure (overrides exception handler)
    
    # Error handling
    exception_handlers: List[ExceptionHandler] = Field(default_factory=list)
    compensations: List[CompensationAction] = Field(default_factory=list)
    
    # Execution configuration
    timeout_ms: Optional[int] = None
    skip_on_condition: Optional[str] = None  # Skip this step if condition is true
    
    def validate_step(self) -> bool:
        """Validate that the step configuration is correct."""
        type_specs = {
            "task": self.task_spec,
            "parallel": self.parallel_spec,
            "conditional": self.conditional_spec,
            "loop": self.loop_spec
        }
        
        # Exactly one spec should be set for the step type
        spec = type_specs.get(self.type)
        if spec is None:
            return False
        
        # Other specs should be None
        for step_type, step_spec in type_specs.items():
            if step_type != self.type and step_spec is not None:
                return False
        
        return True


class WorkflowDefinition(BaseModel):
    """Complete workflow definition."""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    description: Optional[str] = None
    version: int = 1
    
    # Workflow structure
    entry_point: str  # ID of the first step to execute
    steps: Dict[str, WorkflowStep] = Field(default_factory=dict)
    
    # Global configuration
    global_timeout_ms: Optional[int] = None
    global_exception_handlers: List[ExceptionHandler] = Field(default_factory=list)
    
    # Metadata
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    is_active: bool = True
    
    def add_step(self, step: WorkflowStep) -> 'WorkflowDefinition':
        """Add a step to the workflow."""
        if not step.validate_step():
            raise ValueError(f"Invalid step configuration for step {step.id}")
        
        self.steps[step.id] = step
        return self
    
    def get_entry_step(self) -> Optional[WorkflowStep]:
        """Get the entry point step."""
        return self.steps.get(self.entry_point)
    
    def get_next_steps(self, current_step_id: str, success: bool = True) -> List[str]:
        """Get the next step IDs based on the current step outcome."""
        step = self.steps.get(current_step_id)
        if not step:
            return []
        
        if success and step.on_success:
            return [step.on_success]
        elif not success and step.on_failure:
            return [step.on_failure]
        
        return []
    
    def validate_workflow(self) -> List[str]:
        """Validate the complete workflow and return any errors."""
        errors = []
        
        # Check entry point exists
        if self.entry_point not in self.steps:
            errors.append(f"Entry point '{self.entry_point}' not found in steps")
        
        # Validate all steps
        for step_id, step in self.steps.items():
            if not step.validate_step():
                errors.append(f"Step '{step_id}' has invalid configuration")
            
            # Check step references
            if step.on_success and step.on_success not in self.steps:
                errors.append(f"Step '{step_id}' references non-existent success step '{step.on_success}'")
            
            if step.on_failure and step.on_failure not in self.steps:
                errors.append(f"Step '{step_id}' references non-existent failure step '{step.on_failure}'")
        
        return errors


class WorkflowStore:
    """Storage and retrieval for workflow definitions."""
    
    def __init__(self, database_path: str = "events.db"):
        self.database_path = database_path
        
    def save_workflow(self, workflow: WorkflowDefinition) -> None:
        """Save a workflow definition to storage."""
        with sqlite3.connect(self.database_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO workflows (
                    id, name, definition_json, version, is_active, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    workflow.id,
                    workflow.name,
                    workflow.model_dump_json(),
                    workflow.version,
                    workflow.is_active,
                    workflow.created_at.isoformat()
                )
            )
            
        logger.info(
            "Workflow saved",
            workflow_id=workflow.id,
            name=workflow.name,
            version=workflow.version
        )
    
    def get_workflow(self, workflow_id: str) -> Optional[WorkflowDefinition]:
        """Get a workflow by ID."""
        with sqlite3.connect(self.database_path) as conn:
            cursor = conn.execute(
                "SELECT definition_json FROM workflows WHERE id = ? AND is_active = 1",
                (workflow_id,)
            )
            
            row = cursor.fetchone()
            if row:
                return WorkflowDefinition.model_validate_json(row[0])
        
        return None
    
    def find_workflow(self, name: str, version: Optional[int] = None) -> Optional[WorkflowDefinition]:
        """Find a workflow by name and optionally version."""
        with sqlite3.connect(self.database_path) as conn:
            if version:
                cursor = conn.execute(
                    """
                    SELECT definition_json FROM workflows 
                    WHERE name = ? AND version = ? AND is_active = 1
                    """,
                    (name, version)
                )
            else:
                cursor = conn.execute(
                    """
                    SELECT definition_json FROM workflows 
                    WHERE name = ? AND is_active = 1 
                    ORDER BY version DESC LIMIT 1
                    """,
                    (name,)
                )
            
            row = cursor.fetchone()
            if row:
                return WorkflowDefinition.model_validate_json(row[0])
        
        return None
    
    def list_workflows(self, active_only: bool = True) -> List[WorkflowDefinition]:
        """List all workflows."""
        with sqlite3.connect(self.database_path) as conn:
            if active_only:
                cursor = conn.execute(
                    "SELECT definition_json FROM workflows WHERE is_active = 1 ORDER BY name, version"
                )
            else:
                cursor = conn.execute(
                    "SELECT definition_json FROM workflows ORDER BY name, version"
                )
            
            workflows = []
            for row in cursor.fetchall():
                workflows.append(WorkflowDefinition.model_validate_json(row[0]))
            
            return workflows
    
    def deactivate_workflow(self, workflow_id: str) -> bool:
        """Deactivate a workflow."""
        with sqlite3.connect(self.database_path) as conn:
            cursor = conn.execute(
                "UPDATE workflows SET is_active = 0 WHERE id = ?",
                (workflow_id,)
            )
            
            return cursor.rowcount > 0
    
    def get_workflow_by_task_type(self, task_type: str) -> Optional[WorkflowDefinition]:
        """Find a workflow that can handle a specific task type."""
        # This is a simple implementation - in practice you might want more
        # sophisticated matching based on task type patterns or capabilities
        return self.find_workflow(task_type)