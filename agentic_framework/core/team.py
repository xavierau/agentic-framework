"""Team orchestration classes."""

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, TYPE_CHECKING
from uuid import uuid4
import structlog

from pydantic import BaseModel, Field

from ..messaging.base import MessageBus, Message, MessageType
from .agent import Agent, AgentStatus
from .task import Task, TaskResult, TaskStatus, TaskPriority

if TYPE_CHECKING:
    from ..workspace import Workspace


logger = structlog.get_logger()


class TeamMember(BaseModel):
    """Represents a team member with role and metadata."""
    
    agent_id: str
    role: str = "member"
    joined_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        use_enum_values = True


class Team(BaseModel):
    """Represents a team of agents."""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    description: Optional[str] = None
    lead_id: Optional[str] = None
    
    # Team composition
    members: Dict[str, TeamMember] = Field(default_factory=dict)
    child_teams: Set[str] = Field(default_factory=set)  # Teams that are members of this team
    parent_teams: Set[str] = Field(default_factory=set)  # Teams this team belongs to
    
    # Configuration
    max_concurrent_tasks: int = 10
    auto_assign_tasks: bool = True
    
    # Runtime state
    active_tasks: Set[str] = Field(default_factory=set)
    completed_tasks: int = 0
    failed_tasks: int = 0
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        use_enum_values = True
        arbitrary_types_allowed = True
    
    def __init__(self, **data):
        super().__init__(**data)
        # Dependencies (will be injected) - private attributes not in Pydantic model
        self._message_bus: Optional[MessageBus] = None
        self._agent_registry: Dict[str, Agent] = {}
        self._child_team_registry: Dict[str, "Team"] = {}
        self._running: bool = False
    
    def set_message_bus(self, message_bus: MessageBus) -> None:
        """Set the message bus for this team."""
        self._message_bus = message_bus
    
    def register_agent(self, agent: Agent) -> None:
        """Register an agent in the local registry."""
        self._agent_registry[agent.id] = agent
    
    def register_child_team(self, team: "Team") -> None:
        """Register a child team in the local registry."""
        self._child_team_registry[team.id] = team
    
    def add_member(self, agent_id: str, role: str = "member") -> None:
        """Add an agent as a team member."""
        member = TeamMember(agent_id=agent_id, role=role)
        self.members[agent_id] = member
        
        logger.info(
            "Member added to team",
            team_id=self.id,
            team_name=self.name,
            agent_id=agent_id,
            role=role
        )
    
    def remove_member(self, agent_id: str) -> None:
        """Remove an agent from the team."""
        if agent_id in self.members:
            del self.members[agent_id]
            logger.info(
                "Member removed from team",
                team_id=self.id,
                team_name=self.name,
                agent_id=agent_id
            )
    
    def add_child_team(self, team_id: str, role: str = "member") -> None:
        """Add another team as a member of this team."""
        self.child_teams.add(team_id)
        # Also add as a regular member for unified handling
        member = TeamMember(agent_id=team_id, role=role)
        self.members[team_id] = member
        
        logger.info(
            "Child team added",
            team_id=self.id,
            team_name=self.name,
            child_team_id=team_id,
            role=role
        )
    
    def set_lead(self, agent_id: str) -> None:
        """Set the team lead."""
        if agent_id not in self.members:
            raise ValueError(f"Agent {agent_id} is not a member of team {self.id}")
        
        self.lead_id = agent_id
        self.members[agent_id].role = "lead"
        
        logger.info(
            "Team lead set",
            team_id=self.id,
            team_name=self.name,
            lead_id=agent_id
        )
    
    def get_available_agents(self) -> List[Agent]:
        """Get list of available agents in the team."""
        available = []
        
        for member_id in self.members:
            if member_id in self._agent_registry:
                agent = self._agent_registry[member_id]
                if agent.status == AgentStatus.ACTIVE and agent.can_accept_task:
                    available.append(agent)
            elif member_id in self._child_team_registry:
                # Recursively get available agents from child teams
                child_team = self._child_team_registry[member_id]
                available.extend(child_team.get_available_agents())
        
        return available
    
    def get_agents_with_capabilities(self, required_capabilities: List[str]) -> List[Agent]:
        """Get agents that have the required capabilities."""
        capable_agents = []
        
        for agent in self.get_available_agents():
            if agent.has_capabilities(required_capabilities):
                capable_agents.append(agent)
        
        return capable_agents
    
    @property
    def capabilities(self) -> Set[str]:
        """Get all capabilities available in this team from agents and child teams."""
        caps = set()
        
        # From registered agents
        for agent in self._agent_registry.values():
            caps.update(cap.name for cap in agent.capabilities)
        
        # From child teams
        for child_team in self._child_team_registry.values():
            caps.update(child_team.capabilities)
        
        return caps
    
    async def execute(self, task: Task) -> TaskResult:
        """
        Execute a task directly on this team.
        
        This method provides a simple way to execute tasks on teams without
        going through the full workspace orchestration.
        """
        try:
            # Check if team can handle the task
            if task.required_capabilities:
                capable_agents = self.get_agents_with_capabilities(task.required_capabilities)
                if not capable_agents:
                    return TaskResult.failure_result(
                        error_message=f"No agents with required capabilities: {task.required_capabilities}",
                        metadata={"team_id": self.id}
                    )
            else:
                # If no specific capabilities required, use any available agent
                capable_agents = self.get_available_agents()
                if not capable_agents:
                    return TaskResult.failure_result(
                        error_message="No available agents in team",
                        metadata={"team_id": self.id}
                    )
            
            # Assign task to first capable agent
            assigned_agent = capable_agents[0]
            task.assigned_team_id = self.id
            task.assigned_agent_id = assigned_agent.id
            
            # Add to active tasks
            self.active_tasks.add(task.id)
            
            logger.info(
                "Executing task directly on team",
                team_id=self.id,
                task_id=task.id,
                assigned_agent_id=assigned_agent.id
            )
            
            # Execute task on agent
            result = await assigned_agent.execute_task(task)
            
            # Update team stats based on result
            self.active_tasks.discard(task.id)
            if result.success:
                self.completed_tasks += 1
            else:
                self.failed_tasks += 1
            
            return result
            
        except Exception as e:
            self.active_tasks.discard(task.id)
            self.failed_tasks += 1
            
            logger.error(
                "Error executing task on team",
                team_id=self.id,
                task_id=task.id,
                error=str(e)
            )
            
            return TaskResult.failure_result(
                error_message=f"Team execution error: {str(e)}",
                metadata={"team_id": self.id, "task_id": task.id}
            )
    
    async def start(self) -> None:
        """Start the team."""
        if self._running:
            return
            
        self._running = True
        
        if self._message_bus:
            await self._message_bus.subscribe(f"team.{self.id}", self._handle_team_message)
        
        logger.info("Team started", team_id=self.id, team_name=self.name)
    
    async def stop(self) -> None:
        """Stop the team."""
        self._running = False
        
        if self._message_bus:
            await self._message_bus.unsubscribe(f"team.{self.id}")
        
        logger.info("Team stopped", team_id=self.id, team_name=self.name)
    
    async def assign_task(self, task: Task) -> bool:
        """Assign a task to an appropriate team member."""
        if len(self.active_tasks) >= self.max_concurrent_tasks:
            return False
        
        # Find suitable agent
        suitable_agents = self.get_agents_with_capabilities(task.required_capabilities)
        if not suitable_agents:
            logger.warning(
                "No suitable agents found for task",
                team_id=self.id,
                task_id=task.id,
                required_capabilities=task.required_capabilities
            )
            return False
        
        # Simple assignment strategy - pick first available
        # TODO: Implement more sophisticated assignment strategies
        assigned_agent = suitable_agents[0]
        
        task.assigned_team_id = self.id
        task.assigned_agent_id = assigned_agent.id
        self.active_tasks.add(task.id)
        
        # Send task assignment message
        if self._message_bus:
            message = Message.create(
                sender_id=self.id,
                receiver_id=assigned_agent.id,
                message_type=MessageType.TASK_ASSIGNED,
                content={"task": task.to_dict()},
                task_id=task.id
            )
            await self._message_bus.send_to_agent(assigned_agent.id, message)
        
        logger.info(
            "Task assigned",
            team_id=self.id,
            task_id=task.id,
            agent_id=assigned_agent.id
        )
        
        return True
    
    async def _handle_team_message(self, message: Message) -> None:
        """Handle messages sent to the team."""
        try:
            if message.message_type == MessageType.TEAM_TASK_REQUEST:
                # Handle task request
                task_data = message.content.get("task")
                if task_data:
                    task = Task(**task_data)
                    await self.assign_task(task)
            
            elif message.message_type == MessageType.TASK_COMPLETED:
                # Handle task completion
                task_id = message.content.get("task_id")
                if task_id and task_id in self.active_tasks:
                    self.active_tasks.discard(task_id)
                    
                    result = message.content.get("result", {})
                    if result.get("success", False):
                        self.completed_tasks += 1
                    else:
                        self.failed_tasks += 1
            
            elif message.message_type == MessageType.TASK_FAILED:
                # Handle task failure
                task_id = message.content.get("task_id")
                if task_id and task_id in self.active_tasks:
                    self.active_tasks.discard(task_id)
                    self.failed_tasks += 1
            
        except Exception as e:
            logger.error(
                "Error handling team message",
                team_id=self.id,
                message_id=message.id,
                error=str(e)
            )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get team statistics."""
        available_agents = self.get_available_agents()
        total_capabilities = set()
        for agent in available_agents:
            total_capabilities.update(c.name for c in agent.capabilities)
        
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "lead_id": self.lead_id,
            "member_count": len(self.members),
            "child_team_count": len(self.child_teams),
            "available_agents": len(available_agents),
            "active_tasks": len(self.active_tasks),
            "completed_tasks": self.completed_tasks,
            "failed_tasks": self.failed_tasks,
            "success_rate": self.completed_tasks / (self.completed_tasks + self.failed_tasks) if (self.completed_tasks + self.failed_tasks) > 0 else 0,
            "total_capabilities": list(total_capabilities),
            "created_at": self.created_at.isoformat(),
        }


class TeamLead(Agent):
    """Specialized agent that can lead teams and orchestrate tasks."""
    
    def __init__(self, **data):
        super().__init__(**data)
        self.agent_type = "team_lead"
        self.max_concurrent_tasks = 5  # Team leads can handle more tasks
    
    async def review_task_and_create_plan(self, task: Task, team: Team) -> List[Task]:
        """Review a task and create a plan by breaking it down into subtasks."""
        try:
            # This is a simplified implementation
            # In practice, this would involve more sophisticated planning logic
            
            subtasks = []
            
            # Check if task can be handled directly by team members
            suitable_agents = team.get_agents_with_capabilities(task.required_capabilities)
            
            if suitable_agents and task.task_type in ["simple", "direct"]:
                # Task can be handled directly
                return [task]
            
            # Complex task - break it down
            if task.task_type == "complex":
                # Create subtasks based on the task
                subtasks = await self._decompose_complex_task(task)
            
            # Assign team and parent task relationship
            for subtask in subtasks:
                subtask.parent_task_id = task.id
                task.add_subtask(subtask)
            
            logger.info(
                "Task plan created",
                team_lead_id=self.id,
                task_id=task.id,
                subtasks_count=len(subtasks)
            )
            
            return subtasks
            
        except Exception as e:
            logger.error(
                "Error creating task plan",
                team_lead_id=self.id,
                task_id=task.id,
                error=str(e)
            )
            return [task]  # Fallback to original task
    
    async def _decompose_complex_task(self, task: Task) -> List[Task]:
        """Decompose a complex task into smaller subtasks."""
        # This is a placeholder implementation
        # In practice, this would use AI/ML models or rule-based systems
        
        subtasks = []
        
        # Example decomposition for different task types
        if "analyze" in task.title.lower():
            subtasks.append(Task(
                title=f"Data collection for {task.title}",
                task_type="data_collection",
                input_data=task.input_data,
                required_capabilities=["data_access", "collection"]
            ))
            
            subtasks.append(Task(
                title=f"Analysis for {task.title}",
                task_type="analysis",
                input_data=task.input_data,
                required_capabilities=["analysis", "computation"],
                dependencies=[subtasks[0].id] if subtasks else []
            ))
            
            subtasks.append(Task(
                title=f"Report generation for {task.title}",
                task_type="report_generation",
                input_data=task.input_data,
                required_capabilities=["writing", "reporting"],
                dependencies=[subtasks[1].id] if len(subtasks) > 1 else []
            ))
        
        return subtasks
    
    async def review_results(self, task: Task, subtask_results: List[TaskResult]) -> TaskResult:
        """Review results from subtasks and create final result."""
        try:
            # Check if all subtasks completed successfully
            all_successful = all(result.success for result in subtask_results)
            
            if all_successful:
                # Aggregate results
                combined_data = {}
                combined_metadata = {}
                
                for result in subtask_results:
                    combined_data.update(result.data)
                    combined_metadata.update(result.metadata)
                
                return TaskResult.success_result(
                    data=combined_data,
                    metadata={
                        **combined_metadata,
                        "subtask_count": len(subtask_results),
                        "reviewed_by": self.id
                    }
                )
            else:
                # Some subtasks failed
                failed_count = sum(1 for result in subtask_results if not result.success)
                error_messages = [result.error_message for result in subtask_results if result.error_message]
                
                return TaskResult.failure_result(
                    error_message=f"{failed_count} subtasks failed: {'; '.join(error_messages)}",
                    metadata={
                        "subtask_count": len(subtask_results),
                        "failed_count": failed_count,
                        "reviewed_by": self.id
                    }
                )
                
        except Exception as e:
            return TaskResult.failure_result(
                error_message=f"Error reviewing results: {str(e)}",
                metadata={"reviewed_by": self.id}
            )