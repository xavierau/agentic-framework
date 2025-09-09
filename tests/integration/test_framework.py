"""Integration tests for the complete framework."""

import pytest
import asyncio
from unittest.mock import AsyncMock, Mock

from agentic_framework.framework import AgenticFramework
from agentic_framework.core.task import Task, TaskResult, TaskPriority
from agentic_framework.core.agent import AgentCapability
from agentic_framework.messaging.base import MessageBus


class MockMessageBus(MessageBus):
    """Mock message bus for testing."""
    
    def __init__(self):
        super().__init__()
        self.published_messages = []
        self.subscriptions = {}
        self.connected = False
    
    async def connect(self):
        """Mock connect."""
        self.connected = True
    
    async def disconnect(self):
        """Mock disconnect."""
        self.connected = False
    
    async def publish(self, channel, message):
        """Mock publish - store message."""
        self.published_messages.append((channel, message))
    
    async def subscribe(self, channel, handler):
        """Mock subscribe."""
        if channel not in self.subscriptions:
            self.subscriptions[channel] = []
        self.subscriptions[channel].append(handler)
    
    async def unsubscribe(self, channel, handler=None):
        """Mock unsubscribe."""
        if channel in self.subscriptions:
            if handler:
                try:
                    self.subscriptions[channel].remove(handler)
                except ValueError:
                    pass
            else:
                self.subscriptions[channel] = []


class TestAgenticFramework:
    """Integration tests for AgenticFramework."""
    
    @pytest.fixture
    def framework(self):
        """Create framework instance for testing."""
        mock_bus = MockMessageBus()
        return AgenticFramework(message_bus=mock_bus)
    
    @pytest.mark.asyncio
    async def test_framework_lifecycle(self):
        """Test framework start/stop lifecycle."""
        mock_bus = MockMessageBus()
        framework = AgenticFramework(message_bus=mock_bus)
        
        assert not framework._running
        assert not mock_bus.connected
        
        await framework.start()
        
        assert framework._running
        assert mock_bus.connected
        
        await framework.stop()
        
        assert not framework._running
        assert not mock_bus.connected
    
    @pytest.mark.asyncio
    async def test_create_agent(self, framework):
        """Test agent creation and registration."""
        async with framework:
            agent = framework.create_agent(
                name="TestAgent",
                agent_type="test",
                capabilities=["analysis", "reporting"],
                max_concurrent_tasks=3
            )
            
            assert agent.name == "TestAgent"
            assert agent.agent_type == "test"
            assert agent.max_concurrent_tasks == 3
            assert agent.has_capability("analysis")
            assert agent.has_capability("reporting")
            
            # Check registration
            assert agent.id in framework._agents
            assert framework.get_agent(agent.id) is agent
    
    @pytest.mark.asyncio
    async def test_create_team_lead(self, framework):
        """Test team lead creation."""
        async with framework:
            team_lead = framework.create_team_lead(
                name="TeamLead",
                capabilities=["coordination", "planning"],
                max_concurrent_tasks=5
            )
            
            assert team_lead.agent_type == "team_lead"
            assert team_lead.max_concurrent_tasks == 5
            assert team_lead.has_capability("coordination")
            assert team_lead.has_capability("planning")
    
    @pytest.mark.asyncio
    async def test_create_team(self, framework):
        """Test team creation and configuration."""
        async with framework:
            # Create a team lead first
            lead = framework.create_team_lead(
                name="TeamLead",
                capabilities=["coordination"],
                max_concurrent_tasks=5
            )
            
            team = framework.create_team(
                name="TestTeam",
                description="A test team",
                lead_id=lead.id,
                max_concurrent_tasks=10
            )
            
            assert team.name == "TestTeam"
            assert team.description == "A test team"
            assert team.lead_id == lead.id
            assert team.max_concurrent_tasks == 10
            
            # Check registration
            assert team.id in framework._teams
            assert framework.get_team(team.id) is team
    
    @pytest.mark.asyncio
    async def test_add_agent_to_team(self, framework):
        """Test adding agents to teams."""
        async with framework:
            agent = framework.create_agent(
                name="TestAgent",
                agent_type="test",
                capabilities=["analysis"]
            )
            
            team = framework.create_team(
                name="TestTeam",
                max_concurrent_tasks=5
            )
            
            framework.add_agent_to_team(agent.id, team.id, "member")
            
            assert agent.id in team.members
            assert team.members[agent.id].role == "member"
            assert agent.id in team._agent_registry
    
    @pytest.mark.asyncio
    async def test_add_team_to_team(self, framework):
        """Test team composition (adding team to team)."""
        async with framework:
            child_team = framework.create_team(name="ChildTeam")
            parent_team = framework.create_team(name="ParentTeam")
            
            framework.add_team_to_team(child_team.id, parent_team.id, "specialist")
            
            assert child_team.id in parent_team.child_teams
            assert parent_team.id in child_team.parent_teams
            assert child_team.id in parent_team.members
            assert parent_team.members[child_team.id].role == "specialist"
    
    @pytest.mark.asyncio
    async def test_create_task(self, framework):
        """Test task creation using framework."""
        async with framework:
            task = framework.create_task(
                title="Test Task",
                task_type="analysis",
                description="A test analysis task",
                input_data={"data": "test_data"},
                required_capabilities=["analysis", "reporting"],
                priority=TaskPriority.HIGH
            )
            
            assert task.title == "Test Task"
            assert task.task_type == "analysis"
            assert task.description == "A test analysis task"
            assert task.input_data["data"] == "test_data"
            assert task.required_capabilities == ["analysis", "reporting"]
            assert task.priority == TaskPriority.HIGH
    
    @pytest.mark.asyncio
    async def test_system_status(self, framework):
        """Test getting system status."""
        async with framework:
            # Create some agents and teams
            agent1 = framework.create_agent("Agent1", "type1", ["cap1"])
            agent2 = framework.create_agent("Agent2", "type2", ["cap2"])
            team1 = framework.create_team("Team1")
            team2 = framework.create_team("Team2")
            
            status = framework.get_system_status()
            
            assert status["running"] is True
            assert status["agents"]["total"] == 2
            assert status["teams"]["total"] == 2
            assert "system_load" in status
            assert "timestamp" in status
    
    @pytest.mark.asyncio
    async def test_list_agents_and_teams(self, framework):
        """Test listing agents and teams."""
        async with framework:
            agent = framework.create_agent("TestAgent", "test", ["cap1"])
            team = framework.create_team("TestTeam")
            
            agents = framework.list_agents()
            teams = framework.list_teams()
            
            assert len(agents) == 1
            assert agents[0] is agent
            assert len(teams) == 1
            assert teams[0] is team
    
    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test using framework as async context manager."""
        mock_bus = MockMessageBus()
        
        async with AgenticFramework(message_bus=mock_bus) as framework:
            assert framework._running
            assert mock_bus.connected
            
            # Use framework
            agent = framework.create_agent("TestAgent", "test", ["cap1"])
            assert agent.name == "TestAgent"
        
        # Should be stopped after context exit
        assert not framework._running
        assert not mock_bus.connected


@pytest.mark.asyncio
async def test_complete_workflow():
    """Test a complete workflow from agent creation to task execution."""
    mock_bus = MockMessageBus()
    
    async def test_handler(task):
        """Simple test handler."""
        return TaskResult.success_result({"result": f"processed_{task.title}"})
    
    async with AgenticFramework(message_bus=mock_bus) as framework:
        # Create agents with capabilities
        analyst = framework.create_agent(
            name="Analyst",
            agent_type="analyst", 
            capabilities=["analysis", "data_processing"]
        )
        analyst.register_task_handler("analysis", test_handler)
        
        reporter = framework.create_agent(
            name="Reporter",
            agent_type="reporter",
            capabilities=["reporting", "visualization"]
        )
        reporter.register_task_handler("reporting", test_handler)
        
        # Create team lead
        lead = framework.create_team_lead(
            name="TeamLead",
            capabilities=["coordination", "planning"]
        )
        lead.register_task_handler("coordination", test_handler)
        
        # Create team
        analysis_team = framework.create_team(
            name="Analysis Team",
            description="Data analysis team"
        )
        
        # Add agents to team
        framework.add_agent_to_team(lead.id, analysis_team.id, "lead")
        framework.add_agent_to_team(analyst.id, analysis_team.id, "member")
        framework.add_agent_to_team(reporter.id, analysis_team.id, "member")
        
        # Create and execute task
        task = framework.create_task(
            title="Market Analysis",
            task_type="analysis",
            description="Analyze market trends",
            required_capabilities=["analysis"],
            priority=TaskPriority.HIGH
        )
        
        # Check that agents can handle the task
        assert analyst.can_accept_task(task)
        assert not reporter.can_accept_task(task)  # Missing analysis capability
        
        # Check team has required capabilities
        capable_agents = analysis_team.get_agents_with_capabilities(["analysis"])
        assert len(capable_agents) == 1
        assert capable_agents[0] is analyst
        
        # Verify system status
        status = framework.get_system_status()
        assert status["agents"]["total"] == 3
        assert status["teams"]["total"] == 1
        assert status["running"] is True