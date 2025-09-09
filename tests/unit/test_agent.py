"""Unit tests for Agent class."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock
from datetime import datetime

from agentic_framework.core.agent import Agent, AgentCapability, AgentStatus
from agentic_framework.core.task import Task, TaskResult, TaskStatus
from agentic_framework.messaging.base import MessageBus, Message


class TestAgent:
    """Test cases for Agent class."""
    
    def test_agent_creation(self):
        """Test basic agent creation."""
        agent = Agent(
            name="TestAgent",
            agent_type="test",
            max_concurrent_tasks=2
        )
        
        assert agent.name == "TestAgent"
        assert agent.agent_type == "test"
        assert agent.max_concurrent_tasks == 2
        assert agent.status == AgentStatus.ACTIVE
        assert len(agent.capabilities) == 0
        assert len(agent.current_tasks) == 0
    
    def test_add_capability(self):
        """Test adding capabilities to agent."""
        agent = Agent(name="TestAgent", agent_type="test")
        
        capability = AgentCapability(
            name="data_processing",
            description="Process data files",
            cost=2
        )
        
        agent.add_capability(capability)
        
        assert len(agent.capabilities) == 1
        assert agent.has_capability("data_processing")
        assert not agent.has_capability("nonexistent")
    
    def test_has_capabilities(self):
        """Test checking multiple capabilities."""
        agent = Agent(name="TestAgent", agent_type="test")
        
        cap1 = AgentCapability(name="capability1")
        cap2 = AgentCapability(name="capability2")
        
        agent.add_capability(cap1)
        agent.add_capability(cap2)
        
        assert agent.has_capabilities(["capability1"])
        assert agent.has_capabilities(["capability1", "capability2"])
        assert not agent.has_capabilities(["capability1", "capability2", "capability3"])
    
    def test_register_task_handler(self):
        """Test registering task handlers."""
        agent = Agent(name="TestAgent", agent_type="test")
        
        def test_handler(task):
            return TaskResult.success_result({"result": "test"})
        
        agent.register_task_handler("test_task", test_handler)
        
        assert "test_task" in agent._task_handlers
        assert agent._task_handlers["test_task"] == test_handler
    
    def test_can_accept_task(self):
        """Test task acceptance logic."""
        agent = Agent(name="TestAgent", agent_type="test", max_concurrent_tasks=2)
        
        capability = AgentCapability(name="analysis")
        agent.add_capability(capability)
        
        def handler(task):
            return TaskResult.success_result({})
        agent.register_task_handler("analysis_task", handler)
        
        task = Task(
            title="Test Task",
            task_type="analysis_task",
            required_capabilities=["analysis"]
        )
        
        # Should accept task when agent is available
        assert agent.can_accept_task(task)
        
        # Should not accept when agent is at capacity
        agent.current_tasks = {"task1", "task2"}
        assert not agent.can_accept_task(task)
        
        # Should not accept when missing capabilities
        agent.current_tasks = set()
        task.required_capabilities = ["missing_capability"]
        assert not agent.can_accept_task(task)
        
        # Should not accept when no handler available
        task.required_capabilities = ["analysis"]
        task.task_type = "unknown_task"
        assert not agent.can_accept_task(task)
    
    @pytest.mark.asyncio
    async def test_execute_task_success(self):
        """Test successful task execution."""
        agent = Agent(name="TestAgent", agent_type="test")
        
        capability = AgentCapability(name="test_cap")
        agent.add_capability(capability)
        
        def success_handler(task):
            return TaskResult.success_result({"processed": True})
        
        agent.register_task_handler("test_task", success_handler)
        
        task = Task(
            title="Test Task",
            task_type="test_task",
            required_capabilities=["test_cap"]
        )
        
        result = await agent.execute_task(task)
        
        assert result.success
        assert result.data["processed"] is True
        assert task.status == TaskStatus.COMPLETED
        assert agent.completed_tasks == 1
        assert agent.failed_tasks == 0
    
    @pytest.mark.asyncio
    async def test_execute_task_failure(self):
        """Test task execution failure."""
        agent = Agent(name="TestAgent", agent_type="test")
        
        capability = AgentCapability(name="test_cap")
        agent.add_capability(capability)
        
        def failure_handler(task):
            raise ValueError("Task processing failed")
        
        agent.register_task_handler("test_task", failure_handler)
        
        task = Task(
            title="Test Task",
            task_type="test_task",
            required_capabilities=["test_cap"]
        )
        
        result = await agent.execute_task(task)
        
        assert not result.success
        assert "Task processing failed" in result.error_message
        assert task.status == TaskStatus.FAILED
        assert agent.completed_tasks == 0
        assert agent.failed_tasks == 1
    
    @pytest.mark.asyncio
    async def test_execute_async_handler(self):
        """Test execution with async task handler."""
        agent = Agent(name="TestAgent", agent_type="test")
        
        capability = AgentCapability(name="async_cap")
        agent.add_capability(capability)
        
        async def async_handler(task):
            await asyncio.sleep(0.1)  # Simulate async work
            return TaskResult.success_result({"async": True})
        
        agent.register_task_handler("async_task", async_handler)
        
        task = Task(
            title="Async Task",
            task_type="async_task",
            required_capabilities=["async_cap"]
        )
        
        result = await agent.execute_task(task)
        
        assert result.success
        assert result.data["async"] is True
    
    def test_get_stats(self):
        """Test agent statistics."""
        agent = Agent(name="TestAgent", agent_type="test")
        agent.completed_tasks = 10
        agent.failed_tasks = 2
        
        stats = agent.get_stats()
        
        assert stats["name"] == "TestAgent"
        assert stats["completed_tasks"] == 10
        assert stats["failed_tasks"] == 2
        assert stats["success_rate"] == 10/12  # 10/(10+2)
    
    def test_to_dict(self):
        """Test agent serialization."""
        agent = Agent(
            name="TestAgent",
            agent_type="test",
            max_concurrent_tasks=3
        )
        
        capability = AgentCapability(name="test_cap", description="Test capability")
        agent.add_capability(capability)
        
        data = agent.to_dict()
        
        assert data["name"] == "TestAgent"
        assert data["agent_type"] == "test"
        assert data["max_concurrent_tasks"] == 3
        assert len(data["capabilities"]) == 1
        assert data["capabilities"][0]["name"] == "test_cap"


class TestAgentCapability:
    """Test cases for AgentCapability class."""
    
    def test_capability_creation(self):
        """Test capability creation."""
        capability = AgentCapability(
            name="data_processing",
            description="Process various data formats",
            parameters={"max_size": "100MB"},
            cost=3
        )
        
        assert capability.name == "data_processing"
        assert capability.description == "Process various data formats"
        assert capability.parameters["max_size"] == "100MB"
        assert capability.cost == 3
    
    def test_capability_hash(self):
        """Test capability hashing for set operations."""
        cap1 = AgentCapability(name="test")
        cap2 = AgentCapability(name="test")
        cap3 = AgentCapability(name="different")
        
        # Same name should hash the same
        assert hash(cap1) == hash(cap2)
        assert hash(cap1) != hash(cap3)
        
        # Should work in sets
        capability_set = {cap1, cap2, cap3}
        assert len(capability_set) == 2  # cap1 and cap2 are considered equal