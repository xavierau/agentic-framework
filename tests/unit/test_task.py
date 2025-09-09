"""Unit tests for Task and TaskResult classes."""

import pytest
from datetime import datetime, timedelta
from agentic_framework.core.task import (
    Task, TaskResult, TaskStatus, TaskPriority, TaskBuilder
)


class TestTaskResult:
    """Test cases for TaskResult class."""
    
    def test_success_result(self):
        """Test creating successful task result."""
        data = {"output": "test_result", "count": 42}
        metadata = {"processing_time": 1.5}
        
        result = TaskResult.success_result(data, metadata)
        
        assert result.success is True
        assert result.data == data
        assert result.metadata == metadata
        assert result.error_message is None
    
    def test_failure_result(self):
        """Test creating failed task result."""
        error_msg = "Processing failed due to invalid input"
        metadata = {"error_code": 500}
        
        result = TaskResult.failure_result(error_msg, metadata)
        
        assert result.success is False
        assert result.error_message == error_msg
        assert result.metadata == metadata
        assert result.data == {}


class TestTask:
    """Test cases for Task class."""
    
    def test_task_creation(self):
        """Test basic task creation."""
        task = Task(
            title="Test Task",
            task_type="test",
            description="A test task",
            priority=TaskPriority.HIGH
        )
        
        assert task.title == "Test Task"
        assert task.task_type == "test"
        assert task.description == "A test task"
        assert task.priority == TaskPriority.HIGH
        assert task.status == TaskStatus.PENDING
        assert task.parent_task_id is None
        assert len(task.subtask_ids) == 0
        assert len(task.dependencies) == 0
    
    def test_task_start(self):
        """Test starting a task."""
        task = Task(title="Test Task", task_type="test")
        
        assert task.status == TaskStatus.PENDING
        assert task.started_at is None
        
        task.start()
        
        assert task.status == TaskStatus.IN_PROGRESS
        assert task.started_at is not None
        assert isinstance(task.started_at, datetime)
    
    def test_task_start_invalid_status(self):
        """Test starting task from invalid status."""
        task = Task(title="Test Task", task_type="test")
        task.status = TaskStatus.COMPLETED
        
        with pytest.raises(ValueError, match="Cannot start task in status"):
            task.start()
    
    def test_task_complete_success(self):
        """Test completing task successfully."""
        task = Task(title="Test Task", task_type="test")
        task.start()
        
        result = TaskResult.success_result({"output": "completed"})
        task.complete(result)
        
        assert task.status == TaskStatus.COMPLETED
        assert task.result == result
        assert task.completed_at is not None
        assert isinstance(task.completed_at, datetime)
    
    def test_task_complete_failure(self):
        """Test completing task with failure."""
        task = Task(title="Test Task", task_type="test")
        task.start()
        
        result = TaskResult.failure_result("Task failed")
        task.complete(result)
        
        assert task.status == TaskStatus.FAILED
        assert task.result == result
        assert task.completed_at is not None
    
    def test_task_complete_invalid_status(self):
        """Test completing task from invalid status."""
        task = Task(title="Test Task", task_type="test")
        # Don't start task - should still be PENDING
        
        result = TaskResult.success_result({})
        
        with pytest.raises(ValueError, match="Cannot complete task in status"):
            task.complete(result)
    
    def test_task_cancel(self):
        """Test cancelling a task."""
        task = Task(title="Test Task", task_type="test")
        reason = "User requested cancellation"
        
        task.cancel(reason)
        
        assert task.status == TaskStatus.CANCELLED
        assert task.completed_at is not None
        assert task.metadata["cancellation_reason"] == reason
    
    def test_task_cancel_invalid_status(self):
        """Test cancelling completed task."""
        task = Task(title="Test Task", task_type="test")
        task.status = TaskStatus.COMPLETED
        
        with pytest.raises(ValueError, match="Cannot cancel task in status"):
            task.cancel()
    
    def test_add_subtask(self):
        """Test adding subtasks."""
        parent_task = Task(title="Parent Task", task_type="parent")
        child_task = Task(title="Child Task", task_type="child")
        
        parent_task.add_subtask(child_task)
        
        assert child_task.parent_task_id == parent_task.id
        assert child_task.id in parent_task.subtask_ids
    
    def test_is_ready_to_start(self):
        """Test checking if task is ready to start."""
        task = Task(
            title="Test Task",
            task_type="test",
            dependencies=["dep1", "dep2"]
        )
        
        # Not ready - dependencies not completed
        assert not task.is_ready_to_start(set())
        assert not task.is_ready_to_start({"dep1"})
        
        # Ready - all dependencies completed
        assert task.is_ready_to_start({"dep1", "dep2"})
        assert task.is_ready_to_start({"dep1", "dep2", "extra_dep"})
        
        # Not ready - task already started
        task.start()
        assert not task.is_ready_to_start({"dep1", "dep2"})
    
    def test_is_overdue(self):
        """Test overdue detection."""
        # Task without deadline is never overdue
        task = Task(title="Test Task", task_type="test")
        assert not task.is_overdue()
        
        # Task with future deadline is not overdue
        task.deadline = datetime.utcnow() + timedelta(hours=1)
        assert not task.is_overdue()
        
        # Task with past deadline is overdue
        task.deadline = datetime.utcnow() - timedelta(hours=1)
        assert task.is_overdue()
        
        # Completed task is not overdue even if past deadline
        task.status = TaskStatus.COMPLETED
        assert not task.is_overdue()
    
    def test_get_duration(self):
        """Test duration calculation."""
        task = Task(title="Test Task", task_type="test")
        
        # No duration if not started
        assert task.get_duration() is None
        
        # Set timestamps manually for testing
        start_time = datetime.utcnow()
        end_time = start_time + timedelta(seconds=30)
        
        task.started_at = start_time
        task.completed_at = end_time
        
        duration = task.get_duration()
        assert duration == 30
    
    def test_to_dict(self):
        """Test task serialization."""
        task = Task(
            title="Test Task",
            task_type="test",
            description="Test description",
            priority=TaskPriority.HIGH,
            required_capabilities=["cap1", "cap2"],
            dependencies=["dep1"],
            estimated_duration=300
        )
        
        data = task.to_dict()
        
        assert data["title"] == "Test Task"
        assert data["task_type"] == "test"
        assert data["description"] == "Test description"
        assert data["priority"] == TaskPriority.HIGH
        assert data["required_capabilities"] == ["cap1", "cap2"]
        assert data["dependencies"] == ["dep1"]
        assert data["estimated_duration"] == 300
        assert data["status"] == TaskStatus.PENDING


class TestTaskBuilder:
    """Test cases for TaskBuilder class."""
    
    def test_basic_build(self):
        """Test basic task building."""
        task = (TaskBuilder("Test Task", "test_type")
                .description("Test description")
                .priority(TaskPriority.HIGH)
                .build())
        
        assert task.title == "Test Task"
        assert task.task_type == "test_type"
        assert task.description == "Test description"
        assert task.priority == TaskPriority.HIGH
    
    def test_complex_build(self):
        """Test building task with all options."""
        input_data = {"param1": "value1", "param2": 42}
        capabilities = ["cap1", "cap2"]
        dependencies = ["dep1", "dep2"]
        deadline = datetime.utcnow() + timedelta(hours=2)
        
        task = (TaskBuilder("Complex Task", "complex")
                .description("A complex task")
                .priority(TaskPriority.CRITICAL)
                .input_data(input_data)
                .required_capabilities(capabilities)
                .dependencies(dependencies)
                .estimated_duration(1800)
                .deadline(deadline)
                .metadata(project="test_project", version="1.0")
                .build())
        
        assert task.title == "Complex Task"
        assert task.task_type == "complex"
        assert task.description == "A complex task"
        assert task.priority == TaskPriority.CRITICAL
        assert task.input_data == input_data
        assert task.required_capabilities == capabilities
        assert task.dependencies == dependencies
        assert task.estimated_duration == 1800
        assert task.deadline == deadline
        assert task.metadata["project"] == "test_project"
        assert task.metadata["version"] == "1.0"
    
    def test_method_chaining(self):
        """Test that all builder methods return self for chaining."""
        builder = TaskBuilder("Test", "test")
        
        # All methods should return the same builder instance
        assert builder.description("test") is builder
        assert builder.priority(TaskPriority.LOW) is builder
        assert builder.input_data({}) is builder
        assert builder.required_capabilities([]) is builder
        assert builder.dependencies([]) is builder
        assert builder.estimated_duration(100) is builder
        assert builder.deadline(datetime.utcnow()) is builder
        assert builder.metadata(key="value") is builder