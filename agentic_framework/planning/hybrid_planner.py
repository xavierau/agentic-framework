"""Hybrid planner combining deterministic workflows with agentic planning."""

import asyncio
from typing import Dict, List, Optional, Any, Union, Literal
from uuid import uuid4
from pydantic import BaseModel, Field
import structlog

from ..core.task import Task, TaskStatus, TaskPriority
from ..core.team import Team
from ..core.agent import Agent
from ..events.event_types import (
    Event, WorkflowExecutionStarted, WorkflowStepScheduled, PlanCreated
)
from .workflow import WorkflowDefinition, WorkflowStep, WorkflowStore, TaskSpec
from .exceptions import ExceptionHandler, RetryPolicy


logger = structlog.get_logger()


class ExecutionPlan(BaseModel):
    """Represents an execution plan for tasks."""
    
    plan_id: str = Field(default_factory=lambda: str(uuid4()))
    root_task_id: str
    plan_type: Literal["workflow", "agentic"] = "agentic"
    
    # For workflow-based plans
    workflow_id: Optional[str] = None
    execution_id: Optional[str] = None
    
    # For agentic plans
    tasks: Dict[str, Task] = Field(default_factory=dict)
    dependencies: Dict[str, List[str]] = Field(default_factory=dict)
    team_assignments: Dict[str, str] = Field(default_factory=dict)
    
    # Common fields
    events: List[Event] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    def is_workflow_based(self) -> bool:
        """Check if this is a workflow-based plan."""
        return self.plan_type == "workflow"
    
    def get_ready_tasks(self, completed_tasks: set[str]) -> List[str]:
        """Get tasks that are ready to execute (for agentic plans)."""
        if self.is_workflow_based():
            return []
        
        ready = []
        for task_id, task in self.tasks.items():
            if (task.status == TaskStatus.PENDING and 
                task_id not in completed_tasks and
                all(dep_id in completed_tasks for dep_id in self.dependencies.get(task_id, []))):
                ready.append(task_id)
        return ready


class AgenticPlanner:
    """AI-driven task decomposition and planning."""
    
    def __init__(self):
        self._team_registry: Dict[str, Team] = {}
        self._agent_registry: Dict[str, Agent] = {}
    
    def register_team(self, team: Team) -> None:
        """Register a team for planning purposes."""
        self._team_registry[team.id] = team
        logger.debug("Team registered with agentic planner", team_id=team.id)
    
    def register_agent(self, agent: Agent) -> None:
        """Register an agent for planning purposes."""
        self._agent_registry[agent.id] = agent
        logger.debug("Agent registered with agentic planner", agent_id=agent.id)
    
    async def decompose_task(self, task: Task, target_team: Team) -> ExecutionPlan:
        """Decompose a task using AI-driven planning."""
        
        # Check if task can be handled directly
        if await self._can_handle_directly(task, target_team):
            logger.info(
                "Task can be handled directly",
                task_id=task.id,
                team_id=target_team.id
            )
            return ExecutionPlan(
                root_task_id=task.id,
                plan_type="agentic",
                tasks={task.id: task},
                team_assignments={task.id: target_team.id}
            )
        
        # Try AI-driven decomposition using team lead
        if target_team.lead_id:
            lead_agent = self._agent_registry.get(target_team.lead_id)
            if hasattr(lead_agent, 'review_task_and_create_plan'):
                try:
                    subtasks = await lead_agent.review_task_and_create_plan(task, target_team)
                    if subtasks and len(subtasks) > 1:
                        logger.info(
                            "Task decomposed by team lead",
                            task_id=task.id,
                            lead_id=target_team.lead_id,
                            subtasks_count=len(subtasks)
                        )
                        return await self._create_agentic_plan(task, subtasks, target_team)
                except Exception as e:
                    logger.warning(
                        "Team lead decomposition failed",
                        task_id=task.id,
                        lead_id=target_team.lead_id,
                        error=str(e)
                    )
        
        # Fallback to rule-based decomposition
        logger.info(
            "Using rule-based decomposition",
            task_id=task.id,
            task_type=task.task_type
        )
        subtasks = await self._rule_based_decomposition(task, target_team)
        return await self._create_agentic_plan(task, subtasks, target_team)
    
    async def _can_handle_directly(self, task: Task, team: Team) -> bool:
        """Check if a task can be handled directly by the team."""
        if hasattr(team, 'get_agents_with_capabilities'):
            suitable_agents = team.get_agents_with_capabilities(task.required_capabilities)
            return len(suitable_agents) > 0
        return False
    
    async def _rule_based_decomposition(self, task: Task, team: Team) -> List[Task]:
        """Decompose task using rule-based logic."""
        subtasks = []
        
        if task.task_type == "complex_analysis":
            # Break into: data_prep -> analysis -> reporting
            prep_task = Task(
                title=f"Data preparation for {task.title}",
                task_type="data_preparation",
                input_data=task.input_data,
                required_capabilities=["data_processing"],
                priority=task.priority,
                parent_task_id=task.id
            )
            
            analysis_task = Task(
                title=f"Analysis phase of {task.title}",
                task_type="analysis",
                input_data=task.input_data,
                required_capabilities=["analysis", "computation"],
                priority=task.priority,
                parent_task_id=task.id
            )
            
            report_task = Task(
                title=f"Reporting for {task.title}",
                task_type="reporting",
                input_data=task.input_data,
                required_capabilities=["writing", "visualization"],
                priority=task.priority,
                parent_task_id=task.id
            )
            
            subtasks = [prep_task, analysis_task, report_task]
            
        elif task.task_type == "multi_step_process":
            # Break into sequential steps
            steps = task.input_data.get("steps", [])
            for i, step in enumerate(steps):
                step_task = Task(
                    title=f"Step {i+1}: {step.get('name', f'Step {i+1}')}",
                    task_type=step.get("type", "generic"),
                    input_data=step.get("data", {}),
                    required_capabilities=step.get("capabilities", ["generic"]),
                    priority=task.priority,
                    parent_task_id=task.id
                )
                subtasks.append(step_task)
        
        else:
            # Default: return the original task
            subtasks = [task]
        
        return subtasks
    
    async def _create_agentic_plan(
        self, 
        root_task: Task, 
        subtasks: List[Task], 
        target_team: Team
    ) -> ExecutionPlan:
        """Create an agentic execution plan from subtasks."""
        
        tasks_dict = {task.id: task for task in subtasks}
        dependencies = {}
        team_assignments = {}
        
        # Build dependencies based on task hierarchy
        for i, task in enumerate(subtasks):
            if i > 0:
                # Each task depends on the previous one (simple sequential)
                dependencies[task.id] = [subtasks[i-1].id]
            
            # Assign all tasks to the target team for now
            # In a more sophisticated implementation, you might have
            # different assignment strategies
            team_assignments[task.id] = target_team.id
        
        return ExecutionPlan(
            root_task_id=root_task.id,
            plan_type="agentic",
            tasks=tasks_dict,
            dependencies=dependencies,
            team_assignments=team_assignments,
            metadata={
                "decomposition_method": "agentic",
                "original_task_type": root_task.task_type,
                "subtasks_count": len(subtasks)
            }
        )


class WorkflowPlanner:
    """Deterministic workflow-based planning."""
    
    def __init__(self, workflow_store: WorkflowStore):
        self.workflow_store = workflow_store
    
    def create_workflow_plan(
        self, 
        task: Task, 
        workflow: WorkflowDefinition
    ) -> ExecutionPlan:
        """Create an execution plan from a workflow definition."""
        
        execution_id = str(uuid4())
        
        # Generate events for workflow execution
        events = []
        
        # Start workflow execution
        start_event = WorkflowExecutionStarted(
            execution_id=execution_id,
            workflow_id=workflow.id,
            task_id=task.id
        )
        events.append(start_event)
        
        # Schedule entry point step
        entry_step = workflow.get_entry_step()
        if entry_step:
            step_event = self._create_step_event(
                execution_id, entry_step, task.input_data
            )
            events.append(step_event)
        
        logger.info(
            "Workflow plan created",
            task_id=task.id,
            workflow_id=workflow.id,
            execution_id=execution_id,
            entry_step=workflow.entry_point
        )
        
        return ExecutionPlan(
            root_task_id=task.id,
            plan_type="workflow",
            workflow_id=workflow.id,
            execution_id=execution_id,
            events=events,
            metadata={
                "workflow_name": workflow.name,
                "workflow_version": workflow.version,
                "entry_point": workflow.entry_point
            }
        )
    
    def _create_step_event(
        self, 
        execution_id: str, 
        step: WorkflowStep, 
        task_data: Dict[str, Any]
    ) -> WorkflowStepScheduled:
        """Create a step scheduled event."""
        
        # Map task data to step data based on step configuration
        step_data = self._map_task_data_to_step(step, task_data)
        
        return WorkflowStepScheduled(
            execution_id=execution_id,
            step_id=step.id,
            step_type=step.type,
            step_data=step_data
        )
    
    def _map_task_data_to_step(
        self, 
        step: WorkflowStep, 
        task_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Map task data to step data using step configuration."""
        
        if step.type == "task" and step.task_spec:
            # Use input mapping if available
            if step.task_spec.input_mapping:
                mapped_data = {}
                for step_key, task_key in step.task_spec.input_mapping.items():
                    if task_key in task_data:
                        mapped_data[step_key] = task_data[task_key]
                return mapped_data
        
        # Default: pass through all task data
        return task_data.copy()


class HybridPlanner:
    """Main planner that combines workflow and agentic approaches."""
    
    def __init__(self, workflow_store: Optional[WorkflowStore] = None):
        self.workflow_store = workflow_store or WorkflowStore()
        self.agentic_planner = AgenticPlanner()
        self.workflow_planner = WorkflowPlanner(self.workflow_store)
    
    def register_team(self, team: Team) -> None:
        """Register a team with both planners."""
        self.agentic_planner.register_team(team)
    
    def register_agent(self, agent: Agent) -> None:
        """Register an agent with both planners."""
        self.agentic_planner.register_agent(agent)
    
    async def create_execution_plan(
        self, 
        task: Task, 
        target_team: Team
    ) -> ExecutionPlan:
        """Create an execution plan using the best available approach."""
        
        logger.info(
            "Creating execution plan",
            task_id=task.id,
            task_type=task.task_type,
            team_id=target_team.id
        )
        
        # 1. Check for predefined workflow
        workflow = None
        if task.workflow_id:
            # Explicit workflow specified
            workflow = self.workflow_store.get_workflow(task.workflow_id)
            logger.info(
                "Using explicit workflow",
                task_id=task.id,
                workflow_id=task.workflow_id
            )
        else:
            # Look for workflow by task type
            workflow = self.workflow_store.get_workflow_by_task_type(task.task_type)
            if workflow:
                logger.info(
                    "Found workflow for task type",
                    task_id=task.id,
                    task_type=task.task_type,
                    workflow_id=workflow.id
                )
        
        # 2. Use workflow if available and valid
        if workflow:
            errors = workflow.validate_workflow()
            if not errors:
                plan = self.workflow_planner.create_workflow_plan(task, workflow)
                
                # Generate plan created event
                plan_event = PlanCreated(
                    plan_id=plan.plan_id,
                    root_task_id=task.id,
                    tasks=[],  # Workflow plans don't have traditional task decomposition
                    dependencies={},
                    metadata={
                        "plan_type": "workflow",
                        "workflow_id": workflow.id
                    }
                )
                plan.events.insert(0, plan_event)
                
                return plan
            else:
                logger.warning(
                    "Workflow validation failed, falling back to agentic planning",
                    task_id=task.id,
                    workflow_id=workflow.id,
                    errors=errors
                )
        
        # 3. Fall back to agentic planning
        logger.info(
            "Using agentic planning",
            task_id=task.id,
            reason="no_workflow_available" if not workflow else "workflow_invalid"
        )
        
        plan = await self.agentic_planner.decompose_task(task, target_team)
        
        # Generate plan created event
        plan_event = PlanCreated(
            plan_id=plan.plan_id,
            root_task_id=task.id,
            tasks=[task.model_dump() for task in plan.tasks.values()],
            dependencies=plan.dependencies,
            metadata={
                "plan_type": "agentic",
                "decomposition_method": "agentic"
            }
        )
        plan.events.insert(0, plan_event)
        
        return plan
    
    def get_workflow_store(self) -> WorkflowStore:
        """Get the workflow store for external access."""
        return self.workflow_store