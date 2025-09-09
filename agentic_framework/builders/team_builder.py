"""
Team builder with fluent interface for creating teams with agents and configurations.
"""

from typing import List, Optional, TYPE_CHECKING, Dict, Any, Callable
from ..core.team import Team, TeamLead
from ..core.agent import Agent, AgentCapability

if TYPE_CHECKING:
    from ..workspace import Workspace


class TeamBuilder:
    """Fluent interface for building teams with agents and configurations."""
    
    def __init__(self, workspace: 'Workspace', name: str):
        self._workspace = workspace
        self._name = name
        self._description: Optional[str] = None
        self._max_concurrent_tasks = 10
        self._agents_to_create: List[Dict[str, Any]] = []
        self._agent_instances_to_add: List[Dict[str, Any]] = []
        self._teams_to_add: List[Dict[str, Any]] = []
        self._lead_to_create: Optional[Dict[str, Any]] = None
    
    def with_description(self, description: str) -> 'TeamBuilder':
        """Set team description."""
        self._description = description
        return self
    
    def max_concurrent(self, count: int) -> 'TeamBuilder':
        """Set maximum concurrent tasks for the team."""
        self._max_concurrent_tasks = count
        return self
    
    def with_lead(self, name: str, capabilities: List[str], max_concurrent_tasks: int = 5) -> 'TeamBuilder':
        """Add a team lead with specified capabilities."""
        self._lead_to_create = {
            "name": name,
            "capabilities": capabilities,
            "max_concurrent_tasks": max_concurrent_tasks
        }
        return self
    
    def with_agent(self, name: str, capabilities: List[str], 
                   max_concurrent_tasks: int = 1, agent_type: str = "worker") -> 'TeamBuilder':
        """Add an agent to the team."""
        self._agents_to_create.append({
            "name": name,
            "capabilities": capabilities,
            "max_concurrent_tasks": max_concurrent_tasks,
            "agent_type": agent_type
        })
        return self
    
    def with_agent_instance(self, agent: Agent, role: str = "member") -> 'TeamBuilder':
        """Add an existing agent instance to the team."""
        self._agent_instances_to_add.append({
            "agent": agent,
            "role": role
        })
        return self
    
    def with_team(self, team: Team, role: str = "member") -> 'TeamBuilder':
        """Add an existing team as a member (team composition)."""
        self._teams_to_add.append({
            "team": team,
            "role": role
        })
        return self
    
    async def build(self) -> Team:
        """Build and return the team with all configured agents and settings."""
        # Create the team
        team = Team(
            name=self._name,
            description=self._description,
            max_concurrent_tasks=self._max_concurrent_tasks
        )
        
        # Create and add team lead if specified
        if self._lead_to_create:
            lead_config = self._lead_to_create
            team_lead = TeamLead(
                name=lead_config["name"],
                agent_type="team_lead",
                max_concurrent_tasks=lead_config["max_concurrent_tasks"]
            )
            
            # Add capabilities
            for cap_name in lead_config["capabilities"]:
                capability = AgentCapability(name=cap_name)
                team_lead.add_capability(capability)
            
            # Register with workspace and team
            self._workspace._agents[team_lead.id] = team_lead
            team.add_member(team_lead.id, "lead")
            team.set_lead(team_lead.id)
            team.register_agent(team_lead)
            
            # Register with orchestration components
            self._workspace.planner.register_agent(team_lead)
            self._workspace.monitor.register_agent(team_lead)
        
        # Create and add agents
        for agent_config in self._agents_to_create:
            agent = Agent(
                name=agent_config["name"],
                agent_type=agent_config["agent_type"],
                max_concurrent_tasks=agent_config["max_concurrent_tasks"]
            )
            
            # Add capabilities
            for cap_name in agent_config["capabilities"]:
                capability = AgentCapability(name=cap_name)
                agent.add_capability(capability)
            
            # Register with workspace and team
            self._workspace._agents[agent.id] = agent
            team.add_member(agent.id, "member")
            team.register_agent(agent)
            
            # Register with orchestration components
            self._workspace.planner.register_agent(agent)
            self._workspace.monitor.register_agent(agent)
        
        # Add existing agent instances
        for agent_config in self._agent_instances_to_add:
            agent = agent_config["agent"]
            role = agent_config["role"]
            
            # Register with workspace and team
            self._workspace._agents[agent.id] = agent
            team.add_member(agent.id, role)
            team.register_agent(agent)
            
            # Register with orchestration components
            self._workspace.planner.register_agent(agent)
            self._workspace.monitor.register_agent(agent)
        
        # Add existing teams as members
        for team_config in self._teams_to_add:
            child_team = team_config["team"]
            role = team_config["role"]
            team.add_child_team(child_team.id, role)
            team.register_child_team(child_team)
            child_team.parent_teams.add(team.id)
        
        # Register team with workspace
        self._workspace._teams[team.id] = team
        
        # Register with orchestration components
        self._workspace.planner.register_team(team)
        self._workspace.dispatcher.register_team(team)
        self._workspace.monitor.register_team(team)
        
        # Start team if workspace is running
        if self._workspace._running:
            team.set_message_bus(self._workspace.message_bus)
            await team.start()
        
        return team