"""Main framework orchestrator that provides the entry point for the agentic framework."""

import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime
import structlog

from .core.agent import Agent, AgentCapability
from .core.team import Team, TeamLead
from .core.task import Task, TaskBuilder, TaskPriority
from .messaging.base import MessageBus
from .messaging.redis_bus import RedisMessageBus
from .messaging.memory_bus import InMemoryMessageBus
from .orchestration.planner import TaskPlanner
from .orchestration.dispatcher import TaskDispatcher
from .orchestration.monitor import ExecutionMonitor


logger = structlog.get_logger()


class AgenticFramework:
    """Main framework class that orchestrates the entire multi-agent system."""
    
    def __init__(self, message_bus: Optional[MessageBus] = None):
        # Core components
        self.message_bus = message_bus or RedisMessageBus()
        self.planner = TaskPlanner()
        self.dispatcher = TaskDispatcher(self.message_bus)
        self.monitor = ExecutionMonitor(self.message_bus)
        
        # Registry
        self._agents: Dict[str, Agent] = {}
        self._teams: Dict[str, Team] = {}
        
        # State
        self._running = False
        
        logger.info("Agentic framework initialized")
    
    async def start(self) -> None:
        """Start the framework and all its components."""
        if self._running:
            return
            
        try:
            # Start message bus
            await self.message_bus.connect()
            
            # Start orchestration components
            await self.dispatcher.start()
            await self.monitor.start()
            
            # Start all registered agents and teams
            for agent in self._agents.values():
                agent.set_message_bus(self.message_bus)
                await agent.start()
            
            for team in self._teams.values():
                team.set_message_bus(self.message_bus)
                await team.start()
            
            self._running = True
            logger.info("Agentic framework started successfully")
            
        except Exception as e:
            logger.error("Failed to start framework", error=str(e))
            await self.stop()
            raise
    
    async def stop(self) -> None:
        """Stop the framework and all its components."""
        if not self._running:
            return
            
        try:
            self._running = False
            
            # Stop all agents and teams
            for agent in self._agents.values():
                await agent.stop()
            
            for team in self._teams.values():
                await team.stop()
            
            # Stop orchestration components
            await self.dispatcher.stop()
            await self.monitor.stop()
            
            # Disconnect message bus
            await self.message_bus.disconnect()
            
            logger.info("Agentic framework stopped successfully")
            
        except Exception as e:
            logger.error("Error stopping framework", error=str(e))
    
    async def create_agent(
        self,
        name: str,
        agent_type: str,
        capabilities: List[str],
        max_concurrent_tasks: int = 1
    ) -> Agent:
        """Create and register a new agent."""
        agent = Agent(
            name=name,
            agent_type=agent_type,
            max_concurrent_tasks=max_concurrent_tasks
        )
        
        # Add capabilities
        for cap_name in capabilities:
            capability = AgentCapability(name=cap_name)
            agent.add_capability(capability)
        
        self._agents[agent.id] = agent
        
        # Register with orchestration components
        self.planner.register_agent(agent)
        self.monitor.register_agent(agent)
        
        # Start agent if framework is running
        if self._running:
            agent.set_message_bus(self.message_bus)
            await agent.start()
        
        logger.info(
            "Agent created and registered",
            agent_id=agent.id,
            name=name,
            agent_type=agent_type,
            capabilities=capabilities
        )
        
        return agent
    
    def create_team_lead(
        self,
        name: str,
        capabilities: List[str],
        max_concurrent_tasks: int = 5
    ) -> TeamLead:
        """Create and register a new team lead agent."""
        team_lead = TeamLead(
            name=name,
            agent_type="team_lead",
            max_concurrent_tasks=max_concurrent_tasks
        )
        
        # Add capabilities
        for cap_name in capabilities:
            capability = AgentCapability(name=cap_name)
            team_lead.add_capability(capability)
        
        self._agents[team_lead.id] = team_lead
        
        # Register with orchestration components
        self.planner.register_agent(team_lead)
        self.monitor.register_agent(team_lead)
        
        logger.info(
            "Team lead created and registered",
            agent_id=team_lead.id,
            name=name,
            capabilities=capabilities
        )
        
        return team_lead
    
    def create_team(
        self,
        name: str,
        description: Optional[str] = None,
        lead_id: Optional[str] = None,
        max_concurrent_tasks: int = 10
    ) -> Team:
        """Create and register a new team."""
        team = Team(
            name=name,
            description=description,
            lead_id=lead_id,
            max_concurrent_tasks=max_concurrent_tasks
        )
        
        self._teams[team.id] = team
        
        # Register with orchestration components
        self.planner.register_team(team)
        self.dispatcher.register_team(team)
        self.monitor.register_team(team)
        
        logger.info(
            "Team created and registered",
            team_id=team.id,
            name=name,
            lead_id=lead_id
        )
        
        return team
    
    async def add_agent_to_team(self, agent_id: str, team_id: str, role: str = "member") -> None:
        """Add an agent to a team."""
        if agent_id not in self._agents:
            raise ValueError(f"Agent {agent_id} not found")
        if team_id not in self._teams:
            raise ValueError(f"Team {team_id} not found")
        
        agent = self._agents[agent_id]
        team = self._teams[team_id]
        
        # Add to team
        team.add_member(agent_id, role)
        
        # Register agent with team
        team.register_agent(agent)
        
        # Set team lead if this is a lead role
        if role == "lead":
            team.set_lead(agent_id)
        
        # Start team if framework is running and team isn't started yet
        if self._running and not team._running:
            team.set_message_bus(self.message_bus)
            await team.start()
        
        logger.info(
            "Agent added to team",
            agent_id=agent_id,
            team_id=team_id,
            role=role
        )
    
    def add_team_to_team(self, child_team_id: str, parent_team_id: str, role: str = "member") -> None:
        """Add a team as a member of another team (composition)."""
        if child_team_id not in self._teams:
            raise ValueError(f"Child team {child_team_id} not found")
        if parent_team_id not in self._teams:
            raise ValueError(f"Parent team {parent_team_id} not found")
        
        parent_team = self._teams[parent_team_id]
        child_team = self._teams[child_team_id]
        
        # Add child team to parent
        parent_team.add_child_team(child_team_id, role)
        
        # Register child team with parent
        parent_team.register_child_team(child_team)
        
        # Update relationships
        child_team.parent_teams.add(parent_team_id)
        parent_team.child_teams.add(child_team_id)
        
        logger.info(
            "Team added to team",
            child_team_id=child_team_id,
            parent_team_id=parent_team_id,
            role=role
        )
    
    async def execute_task(
        self,
        task: Task,
        target_team_id: Optional[str] = None
    ) -> str:
        """Execute a task using the framework's orchestration capabilities."""
        try:
            # Determine target team
            if target_team_id:
                if target_team_id not in self._teams:
                    raise ValueError(f"Team {target_team_id} not found")
                target_team = self._teams[target_team_id]
            else:
                # Find best team for the task
                target_team = await self._find_best_team_for_task(task)
                if not target_team:
                    raise ValueError("No suitable team found for task")
            
            # Create execution plan
            plan = await self.planner.create_execution_plan(task, target_team)
            
            # Execute the plan
            plan_id = await self.dispatcher.execute_plan(plan)
            
            logger.info(
                "Task execution started",
                task_id=task.id,
                plan_id=plan_id,
                target_team_id=target_team.id
            )
            
            return plan_id
            
        except Exception as e:
            logger.error(
                "Error executing task",
                task_id=task.id,
                error=str(e)
            )
            raise
    
    async def _find_best_team_for_task(self, task: Task) -> Optional[Team]:
        """Find the best team to handle a task."""
        best_team = None
        best_score = -1
        
        for team in self._teams.values():
            capable_agents = team.get_agents_with_capabilities(task.required_capabilities)
            if capable_agents:
                score = self._score_team_for_task(team, task, capable_agents)
                if score > best_score:
                    best_score = score
                    best_team = team
        
        return best_team
    
    def _score_team_for_task(self, team: Team, task: Task, capable_agents: List[Agent]) -> float:
        """Score how well a team can handle a task."""
        score = 0.0
        
        # Base score for having capable agents
        score += len(capable_agents) * 10
        
        # Bonus for having multiple capable agents
        if len(capable_agents) > 1:
            score += 20
        
        # Consider team utilization
        utilization = len(team.active_tasks) / max(team.max_concurrent_tasks, 1)
        score -= utilization * 30
        
        # Consider team success rate
        total_tasks = team.completed_tasks + team.failed_tasks
        if total_tasks > 0:
            success_rate = team.completed_tasks / total_tasks
            score += success_rate * 25
        
        return score
    
    def create_task(
        self,
        title: str,
        task_type: str,
        description: Optional[str] = None,
        input_data: Optional[Dict[str, Any]] = None,
        required_capabilities: Optional[List[str]] = None,
        priority: TaskPriority = TaskPriority.NORMAL
    ) -> Task:
        """Create a new task using the task builder."""
        builder = TaskBuilder(title, task_type)
        
        if description:
            builder.description(description)
        
        if input_data:
            builder.input_data(input_data)
        
        if required_capabilities:
            builder.required_capabilities(required_capabilities)
        
        builder.priority(priority)
        
        return builder.build()
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get overall system status."""
        health = self.monitor.get_system_health()
        
        return {
            "running": self._running,
            "agents": {
                "total": len(self._agents),
                "active": health.active_agents,
                "busy": health.busy_agents,
                "error": health.error_agents,
            },
            "teams": {
                "total": len(self._teams),
                "active": health.active_teams,
            },
            "tasks": {
                "total": health.total_tasks,
                "pending": health.pending_tasks,
                "in_progress": health.in_progress_tasks,
                "completed": health.completed_tasks,
                "failed": health.failed_tasks,
            },
            "system_load": health.system_load,
            "average_task_duration": health.average_task_duration,
            "timestamp": health.timestamp.isoformat(),
        }
    
    def get_agent(self, agent_id: str) -> Optional[Agent]:
        """Get an agent by ID."""
        return self._agents.get(agent_id)
    
    def get_team(self, team_id: str) -> Optional[Team]:
        """Get a team by ID."""
        return self._teams.get(team_id)
    
    def list_agents(self) -> List[Agent]:
        """Get list of all registered agents."""
        return list(self._agents.values())
    
    def list_teams(self) -> List[Team]:
        """Get list of all registered teams."""
        return list(self._teams.values())
    
    async def wait_for_completion(self, plan_id: str, timeout: Optional[float] = None) -> bool:
        """Wait for a plan to complete."""
        start_time = datetime.utcnow()
        
        while True:
            status = self.dispatcher.get_plan_status(plan_id)
            if not status:
                return False  # Plan not found
            
            if status["is_complete"]:
                return True
            
            # Check timeout
            if timeout:
                elapsed = (datetime.utcnow() - start_time).total_seconds()
                if elapsed > timeout:
                    return False
            
            await asyncio.sleep(1)
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.stop()