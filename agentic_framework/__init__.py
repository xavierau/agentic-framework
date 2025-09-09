"""
Agentic Framework - A multi-agent framework with team-based orchestration.

This framework provides a hierarchical team structure where agents can form teams,
teams can have team leads that orchestrate tasks, and teams can be composed within
other teams. Communication is handled through pluggable message bus systems.

Key Features:
- Multi-agent coordination with capability-based task assignment
- Hierarchical team structure with team leads
- Team composition (teams as members of other teams)
- Automatic task decomposition and planning
- Parallel and distributed execution
- Real-time monitoring and health tracking
- Pluggable message bus architecture (Redis, SQS, etc.)
- Clean architecture with SOLID principles

Example Usage:

    import asyncio
    from agentic_framework import AgenticFramework, TaskPriority
    
    async def main():
        async with AgenticFramework() as framework:
            # Create agents
            analyst = framework.create_agent(
                name="DataAnalyst",
                agent_type="analyst", 
                capabilities=["analysis", "data_processing"]
            )
            
            # Create team
            team = framework.create_team(name="Analytics Team")
            framework.add_agent_to_team(analyst.id, team.id)
            
            # Execute task
            task = framework.create_task(
                title="Market Analysis",
                task_type="analysis",
                required_capabilities=["analysis"],
                priority=TaskPriority.HIGH
            )
            
            plan_id = await framework.execute_task(task, team.id)
            await framework.wait_for_completion(plan_id)
    
    asyncio.run(main())
"""

from .framework import AgenticFramework
from .workspace import Workspace
from .core.agent import Agent, AgentCapability, AgentStatus
from .core.team import Team, TeamLead
from .core.task import Task, TaskStatus, TaskPriority, TaskResult, TaskBuilder
from .messaging.base import MessageBus, Message, MessageType
from .messaging.redis_bus import RedisMessageBus
from .messaging.memory_bus import InMemoryMessageBus
from .builders import TeamBuilder, AgentBuilder

__version__ = "0.1.0"
__all__ = [
    # Main framework
    "AgenticFramework",  # Backward compatibility
    "Workspace",         # New main class
    
    # Core components
    "Agent", "AgentCapability", "AgentStatus",
    "Team", "TeamLead", 
    "Task", "TaskStatus", "TaskPriority", "TaskResult", "TaskBuilder",
    
    # Builders
    "TeamBuilder", "AgentBuilder",
    
    # Messaging
    "MessageBus", "Message", "MessageType",
    "RedisMessageBus", "InMemoryMessageBus",
]