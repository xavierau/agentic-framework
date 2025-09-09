"""
Workspace orchestrator with hierarchical support and automatic capability discovery.

Replaces the AgenticFramework with a cleaner, more intuitive API that supports
workspace hierarchy and automatic task routing based on capabilities.
"""

import asyncio
from typing import Dict, List, Optional, Any, Set
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
from .builders.team_builder import TeamBuilder
from .builders.agent_builder import AgentBuilder


logger = structlog.get_logger()


class Workspace:
    """
    Main workspace class that orchestrates agents and teams with hierarchical support.
    
    A workspace manages agents, teams, and can contain child workspaces for complex
    organizational structures. Capabilities bubble up from agents through teams to
    workspaces automatically.
    """
    
    def __init__(self, name: str, message_bus: Optional[MessageBus] = None, parent: Optional['Workspace'] = None):
        # Identity
        self.name = name
        self.parent = parent
        self.children: Dict[str, 'Workspace'] = {}
        
        # Core components (only root workspace has these)
        if parent is None:
            self.message_bus = message_bus or InMemoryMessageBus()
            self.planner = TaskPlanner()
            self.dispatcher = TaskDispatcher(self.message_bus)
            self.monitor = ExecutionMonitor(self.message_bus)
        else:
            # Child workspaces share parent's components
            root = self._get_root()
            self.message_bus = root.message_bus
            self.planner = root.planner
            self.dispatcher = root.dispatcher
            self.monitor = root.monitor
        
        # Registry
        self._agents: Dict[str, Agent] = {}
        self._teams: Dict[str, Team] = {}
        
        # State
        self._running = False
        
        logger.info("Workspace initialized", name=name, is_root=parent is None)
    
    def _get_root(self) -> 'Workspace':
        """Get the root workspace."""
        current = self
        while current.parent is not None:
            current = current.parent
        return current
    
    def add(self, child: 'Workspace') -> 'Workspace':
        """Add a child workspace to this workspace."""
        child.parent = self
        self.children[child.name] = child
        logger.info("Child workspace added", parent=self.name, child=child.name)
        return self
    
    def team(self, name: str) -> TeamBuilder:
        """Create a team builder for fluent team creation."""
        return TeamBuilder(self, name)
    
    def agent(self, name: str, agent_type: str = "worker") -> AgentBuilder:
        """Create an agent builder for fluent agent creation."""
        return AgentBuilder(self, name, agent_type)
    
    @property
    def capabilities(self) -> Set[str]:
        """Get all capabilities available in this workspace and its children."""
        caps = set()
        
        # From own agents
        for agent in self._agents.values():
            caps.update(cap.name for cap in agent.capabilities)
        
        # From own teams
        for team in self._teams.values():
            caps.update(team.capabilities)
        
        # From child workspaces
        for child in self.children.values():
            caps.update(child.capabilities)
        
        return caps
    
    def __getitem__(self, name: str) -> 'Workspace':
        """Get child workspace by name."""
        if name not in self.children:
            raise KeyError(f"Child workspace '{name}' not found")
        return self.children[name]
    
    async def start(self) -> None:
        """Start the workspace and all its components."""
        if self._running:
            return
            
        try:
            # Only root workspace starts infrastructure
            if self.parent is None:
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
            
            # Start child workspaces
            for child in self.children.values():
                await child.start()
            
            self._running = True
            logger.info("Workspace started successfully", name=self.name)
            
        except Exception as e:
            logger.error("Failed to start workspace", name=self.name, error=str(e))
            await self.stop()
            raise
    
    async def stop(self) -> None:
        """Stop the workspace and all its components."""
        if not self._running:
            return
            
        try:
            self._running = False
            
            # Stop child workspaces first
            for child in self.children.values():
                await child.stop()
            
            # Stop all agents and teams
            for agent in self._agents.values():
                await agent.stop()
            
            for team in self._teams.values():
                await team.stop()
            
            # Only root workspace stops infrastructure
            if self.parent is None:
                # Stop orchestration components
                await self.dispatcher.stop()
                await self.monitor.stop()
                
                # Disconnect message bus
                await self.message_bus.disconnect()
            
            logger.info("Workspace stopped successfully", name=self.name)
            
        except Exception as e:
            logger.error("Error stopping workspace", name=self.name, error=str(e))
    
    async def execute(self, task: Task, target_team_id: Optional[str] = None) -> str:
        """
        Execute a task using the workspace's orchestration capabilities.
        
        If target_team_id is not specified, automatically finds the best team
        based on task requirements and available capabilities.
        """
        try:
            # Auto-plan task if no requirements specified
            if not task.required_capabilities:
                task = await self._auto_plan_task(task)
            
            # Determine target team
            if target_team_id:
                target_team = self._find_team_by_id(target_team_id)
                if not target_team:
                    raise ValueError(f"Team {target_team_id} not found")
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
                workspace=self.name,
                task_id=task.id,
                plan_id=plan_id,
                target_team_id=target_team.id
            )
            
            return plan_id
            
        except Exception as e:
            logger.error(
                "Error executing task",
                workspace=self.name,
                task_id=task.id,
                error=str(e)
            )
            raise
    
    async def _auto_plan_task(self, task: Task) -> Task:
        """Automatically determine task requirements based on available capabilities and task description."""
        # Simple heuristic-based planning (can be enhanced with LLM in future)
        available_caps = self.capabilities
        suggested_caps = []
        
        task_desc_lower = (task.description or task.title).lower()
        
        # Map keywords to capabilities
        capability_keywords = {
            'data': ['data_collection', 'data_access', 'data_prep'],
            'analysis': ['analysis', 'statistics', 'ml'],
            'report': ['reporting', 'visualization', 'writing'],
            'sales': ['sales_data', 'crm_access'],
            'financial': ['financial_analysis', 'accounting'],
            'ml': ['ml_predictions', 'deep_learning'],
            'compute': ['computation', 'parallel_processing']
        }
        
        for keyword, caps in capability_keywords.items():
            if keyword in task_desc_lower:
                for cap in caps:
                    if cap in available_caps:
                        suggested_caps.append(cap)
        
        # Create new task with suggested capabilities
        if suggested_caps:
            task.required_capabilities = list(set(suggested_caps))
            logger.info(
                "Auto-planned task capabilities",
                task_id=task.id,
                suggested_capabilities=suggested_caps
            )
        
        return task
    
    def _find_team_by_id(self, team_id: str) -> Optional[Team]:
        """Find team by ID in this workspace and children."""
        # Check own teams
        if team_id in self._teams:
            return self._teams[team_id]
        
        # Check child workspaces
        for child in self.children.values():
            team = child._find_team_by_id(team_id)
            if team:
                return team
        
        return None
    
    async def _find_best_team_for_task(self, task: Task) -> Optional[Team]:
        """Find the best team to handle a task across all workspaces."""
        best_team = None
        best_score = -1
        
        # Check teams in all workspaces (self + children)
        for team in self._get_all_teams():
            capable_agents = team.get_agents_with_capabilities(task.required_capabilities)
            if capable_agents:
                score = self._score_team_for_task(team, task, capable_agents)
                if score > best_score:
                    best_score = score
                    best_team = team
        
        return best_team
    
    def _get_all_teams(self) -> List[Team]:
        """Get all teams from this workspace and children."""
        teams = list(self._teams.values())
        for child in self.children.values():
            teams.extend(child._get_all_teams())
        return teams
    
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
        task_type: str = "general",
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
        root = self._get_root()
        health = root.monitor.get_system_health()
        
        # Aggregate stats from all workspaces
        total_agents = len(self._get_all_agents())
        total_teams = len(self._get_all_teams())
        
        return {
            "running": self._running,
            "workspace": self.name,
            "capabilities": list(self.capabilities),
            "agents": {
                "total": total_agents,
                "active": health.active_agents,
                "busy": health.busy_agents,
                "error": health.error_agents,
            },
            "teams": {
                "total": total_teams,
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
            "children": list(self.children.keys())
        }
    
    def _get_all_agents(self) -> List[Agent]:
        """Get all agents from this workspace and children."""
        agents = list(self._agents.values())
        for child in self.children.values():
            agents.extend(child._get_all_agents())
        return agents
    
    def get_agent(self, agent_id: str) -> Optional[Agent]:
        """Get an agent by ID from this workspace or children."""
        if agent_id in self._agents:
            return self._agents[agent_id]
        
        for child in self.children.values():
            agent = child.get_agent(agent_id)
            if agent:
                return agent
        
        return None
    
    def get_team(self, team_id: str) -> Optional[Team]:
        """Get a team by ID from this workspace or children."""
        return self._find_team_by_id(team_id)
    
    def list_agents(self) -> List[Agent]:
        """Get list of all agents in this workspace and children."""
        return self._get_all_agents()
    
    def list_teams(self) -> List[Team]:
        """Get list of all teams in this workspace and children."""
        return self._get_all_teams()
    
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


# Backward compatibility alias
AgenticFramework = Workspace