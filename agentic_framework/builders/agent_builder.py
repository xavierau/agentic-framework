"""
Agent builder with fluent interface for creating agents with capabilities and handlers.
"""

from typing import List, Optional, TYPE_CHECKING, Callable, Any
from ..core.agent import Agent, AgentCapability

if TYPE_CHECKING:
    from ..workspace import Workspace


class AgentBuilder:
    """Fluent interface for building agents with capabilities and handlers."""
    
    def __init__(self, workspace: 'Workspace', name: str, agent_type: str = "worker"):
        self._workspace = workspace
        self._name = name
        self._agent_type = agent_type
        self._max_concurrent_tasks = 1
        self._capabilities: List[str] = []
        self._handlers: dict[str, Callable] = {}
    
    def with_type(self, agent_type: str) -> 'AgentBuilder':
        """Set the agent type."""
        self._agent_type = agent_type
        return self
    
    def with_capabilities(self, *capabilities: str) -> 'AgentBuilder':
        """Add capabilities to the agent."""
        self._capabilities.extend(capabilities)
        return self
    
    def with_capability(self, capability: str) -> 'AgentBuilder':
        """Add a single capability to the agent."""
        self._capabilities.append(capability)
        return self
    
    def max_tasks(self, count: int) -> 'AgentBuilder':
        """Set maximum concurrent tasks for the agent."""
        self._max_concurrent_tasks = count
        return self
    
    def handles(self, task_type: str, handler: Callable) -> 'AgentBuilder':
        """Register a task handler for a specific task type."""
        self._handlers[task_type] = handler
        return self
    
    async def build(self) -> Agent:
        """Build and return the agent with all configured capabilities and handlers."""
        # Create the agent
        agent = Agent(
            name=self._name,
            agent_type=self._agent_type,
            max_concurrent_tasks=self._max_concurrent_tasks
        )
        
        # Add capabilities
        for cap_name in self._capabilities:
            capability = AgentCapability(name=cap_name)
            agent.add_capability(capability)
        
        # Register handlers
        for task_type, handler in self._handlers.items():
            agent.register_task_handler(task_type, handler)
        
        # Register with workspace
        self._workspace._agents[agent.id] = agent
        
        # Register with orchestration components
        self._workspace.planner.register_agent(agent)
        self._workspace.monitor.register_agent(agent)
        
        # Start agent if workspace is running
        if self._workspace._running:
            agent.set_message_bus(self._workspace.message_bus)
            await agent.start()
        
        return agent