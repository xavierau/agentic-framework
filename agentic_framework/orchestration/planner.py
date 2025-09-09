"""Task planning and decomposition components."""

import asyncio
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass
import structlog

from ..core.task import Task, TaskStatus, TaskPriority
from ..core.team import Team, TeamLead
from ..core.agent import Agent


logger = structlog.get_logger()


@dataclass
class ExecutionPlan:
    """Represents an execution plan for a task."""
    
    root_task_id: str
    tasks: Dict[str, Task]
    execution_order: List[List[str]]  # List of task batches that can run in parallel
    dependencies: Dict[str, Set[str]]  # task_id -> set of dependency task_ids
    team_assignments: Dict[str, str]  # task_id -> team_id
    
    def get_ready_tasks(self, completed_tasks: Set[str]) -> List[str]:
        """Get tasks that are ready to execute based on completed dependencies."""
        ready = []
        for task_id, task in self.tasks.items():
            if (task.status == TaskStatus.PENDING and 
                task_id not in completed_tasks and
                all(dep_id in completed_tasks for dep_id in self.dependencies.get(task_id, set()))):
                ready.append(task_id)
        return ready
    
    def is_complete(self) -> bool:
        """Check if all tasks in the plan are complete."""
        return all(
            task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]
            for task in self.tasks.values()
        )


class TaskPlanner:
    """Handles task planning and decomposition."""
    
    def __init__(self):
        self._team_registry: Dict[str, Team] = {}
        self._agent_registry: Dict[str, Agent] = {}
    
    def register_team(self, team: Team) -> None:
        """Register a team for planning purposes."""
        self._team_registry[team.id] = team
    
    def register_agent(self, agent: Agent) -> None:
        """Register an agent for planning purposes."""
        self._agent_registry[agent.id] = agent
    
    async def create_execution_plan(self, root_task: Task, target_team: Team) -> ExecutionPlan:
        """Create an execution plan for a task."""
        try:
            # Step 1: Decompose the task if needed
            tasks = await self._decompose_task(root_task, target_team)
            
            # Step 2: Analyze dependencies
            dependencies = self._analyze_dependencies(tasks)
            
            # Step 3: Create execution order based on dependencies
            execution_order = self._create_execution_order(tasks, dependencies)
            
            # Step 4: Assign tasks to teams
            team_assignments = await self._assign_tasks_to_teams(tasks)
            
            plan = ExecutionPlan(
                root_task_id=root_task.id,
                tasks={task.id: task for task in tasks},
                execution_order=execution_order,
                dependencies=dependencies,
                team_assignments=team_assignments
            )
            
            logger.info(
                "Execution plan created",
                root_task_id=root_task.id,
                total_tasks=len(tasks),
                execution_levels=len(execution_order)
            )
            
            return plan
            
        except Exception as e:
            logger.error(
                "Error creating execution plan",
                root_task_id=root_task.id,
                error=str(e)
            )
            raise
    
    async def _decompose_task(self, task: Task, team: Team) -> List[Task]:
        """Decompose a task into subtasks if needed."""
        # Check if task can be handled directly
        if await self._can_handle_directly(task, team):
            return [task]
        
        # Try to use team lead for decomposition
        if team.lead_id:
            lead_agent = self._agent_registry.get(team.lead_id)
            if isinstance(lead_agent, TeamLead):
                try:
                    subtasks = await lead_agent.review_task_and_create_plan(task, team)
                    if subtasks and len(subtasks) > 1:
                        return subtasks
                except Exception as e:
                    logger.warning(
                        "Team lead decomposition failed, using default",
                        task_id=task.id,
                        lead_id=team.lead_id,
                        error=str(e)
                    )
        
        # Fallback to rule-based decomposition
        return await self._rule_based_decomposition(task, team)
    
    async def _can_handle_directly(self, task: Task, team: Team) -> bool:
        """Check if a task can be handled directly by the team."""
        suitable_agents = team.get_agents_with_capabilities(task.required_capabilities)
        return len(suitable_agents) > 0
    
    async def _rule_based_decomposition(self, task: Task, team: Team) -> List[Task]:
        """Decompose task using rule-based logic."""
        subtasks = []
        
        # Simple rule-based decomposition
        if task.task_type == "complex_analysis":
            # Break into: data_prep -> analysis -> reporting
            prep_task = Task(
                title=f"Data preparation for {task.title}",
                task_type="data_preparation",
                input_data=task.input_data,
                required_capabilities=["data_processing"],
                priority=task.priority
            )
            
            analysis_task = Task(
                title=f"Analysis phase of {task.title}",
                task_type="analysis",
                input_data=task.input_data,
                required_capabilities=["analysis", "computation"],
                dependencies=[prep_task.id],
                priority=task.priority
            )
            
            report_task = Task(
                title=f"Reporting for {task.title}",
                task_type="reporting",
                input_data=task.input_data,
                required_capabilities=["writing", "visualization"],
                dependencies=[analysis_task.id],
                priority=task.priority
            )
            
            # Set up parent-child relationships
            task.add_subtask(prep_task)
            task.add_subtask(analysis_task)
            task.add_subtask(report_task)
            
            subtasks = [prep_task, analysis_task, report_task]
        
        elif task.task_type == "multi_step_process":
            # Break into sequential steps based on input data
            steps = task.input_data.get("steps", [])
            for i, step in enumerate(steps):
                step_task = Task(
                    title=f"Step {i+1}: {step.get('name', f'Step {i+1}')}",
                    task_type=step.get("type", "generic"),
                    input_data=step.get("data", {}),
                    required_capabilities=step.get("capabilities", ["generic"]),
                    dependencies=[subtasks[-1].id] if subtasks else [],
                    priority=task.priority
                )
                task.add_subtask(step_task)
                subtasks.append(step_task)
        
        else:
            # Default: return original task
            subtasks = [task]
        
        return subtasks
    
    def _analyze_dependencies(self, tasks: List[Task]) -> Dict[str, Set[str]]:
        """Analyze dependencies between tasks."""
        dependencies = {}
        task_map = {task.id: task for task in tasks}
        
        for task in tasks:
            deps = set()
            
            # Add explicit dependencies
            for dep_id in task.dependencies:
                if dep_id in task_map:
                    deps.add(dep_id)
            
            # Add parent task dependencies (subtasks depend on their parent being started)
            if task.parent_task_id and task.parent_task_id in task_map:
                parent_task = task_map[task.parent_task_id]
                # Subtasks can start after parent starts, not necessarily after it completes
                # This allows for parallel execution of subtasks
            
            dependencies[task.id] = deps
        
        return dependencies
    
    def _create_execution_order(self, tasks: List[Task], dependencies: Dict[str, Set[str]]) -> List[List[str]]:
        """Create execution order using topological sort."""
        # Kahn's algorithm for topological sorting
        in_degree = {task.id: len(dependencies.get(task.id, set())) for task in tasks}
        
        execution_order = []
        
        while any(degree == 0 for degree in in_degree.values()):
            # Find all tasks with no dependencies (can run in parallel)
            current_batch = [task_id for task_id, degree in in_degree.items() if degree == 0]
            execution_order.append(current_batch)
            
            # Remove these tasks and update dependencies
            for task_id in current_batch:
                in_degree[task_id] = -1  # Mark as processed
                
                # Reduce in-degree for dependent tasks
                for other_task_id, deps in dependencies.items():
                    if task_id in deps:
                        in_degree[other_task_id] -= 1
        
        return execution_order
    
    async def _assign_tasks_to_teams(self, tasks: List[Task]) -> Dict[str, str]:
        """Assign tasks to appropriate teams."""
        assignments = {}
        
        for task in tasks:
            best_team = await self._find_best_team_for_task(task)
            if best_team:
                assignments[task.id] = best_team.id
                task.assigned_team_id = best_team.id
        
        return assignments
    
    async def _find_best_team_for_task(self, task: Task) -> Optional[Team]:
        """Find the best team to handle a task."""
        candidate_teams = []
        
        for team in self._team_registry.values():
            # Check if team has required capabilities
            capable_agents = team.get_agents_with_capabilities(task.required_capabilities)
            if capable_agents:
                # Score team based on various factors
                score = self._score_team_for_task(team, task, capable_agents)
                candidate_teams.append((score, team))
        
        if not candidate_teams:
            return None
        
        # Return team with highest score
        candidate_teams.sort(key=lambda x: x[0], reverse=True)
        return candidate_teams[0][1]
    
    def _score_team_for_task(self, team: Team, task: Task, capable_agents: List[Agent]) -> float:
        """Score how well a team can handle a task."""
        score = 0.0
        
        # Base score for having capable agents
        score += len(capable_agents) * 10
        
        # Bonus for having multiple capable agents (redundancy)
        if len(capable_agents) > 1:
            score += 20
        
        # Penalty for team being busy
        utilization = len(team.active_tasks) / max(team.max_concurrent_tasks, 1)
        score -= utilization * 30
        
        # Bonus for team success rate
        total_tasks = team.completed_tasks + team.failed_tasks
        if total_tasks > 0:
            success_rate = team.completed_tasks / total_tasks
            score += success_rate * 25
        
        # Priority bonus for high-priority tasks
        if task.priority == TaskPriority.CRITICAL:
            score += 50
        elif task.priority == TaskPriority.HIGH:
            score += 25
        
        return score
    
    def optimize_plan(self, plan: ExecutionPlan) -> ExecutionPlan:
        """Optimize an execution plan for better performance."""
        # This is a placeholder for plan optimization logic
        # Could include:
        # - Load balancing across teams
        # - Resource optimization
        # - Critical path analysis
        # - Parallel execution opportunities
        
        logger.info("Plan optimization completed", root_task_id=plan.root_task_id)
        return plan