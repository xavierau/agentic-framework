# Agentic Framework

A multi-agent framework with team-based orchestration, designed for building scalable and distributed agent systems.

## Key Features

🤖 **Multi-Agent Coordination** - Agents with capabilities-based task assignment  
🏢 **Hierarchical Team Structure** - Teams with leads that can orchestrate complex tasks  
🔧 **Team Composition** - Teams can be members of other teams for unlimited scalability  
📋 **Automatic Task Decomposition** - Complex tasks automatically broken into subtasks  
⚡ **Parallel & Distributed Execution** - Message-driven architecture enables true parallelism  
📊 **Real-time Monitoring** - Built-in health tracking and performance metrics  
🔌 **Pluggable Message Bus** - Support for Redis, AWS SQS, and custom implementations  
🏗️ **Clean Architecture** - Built with SOLID principles and dependency injection

## Architecture Overview

```
┌─────────────────────────────────────────┐
│           Agentic Framework             │
├─────────────────────────────────────────┤
│  ┌─────────────┐    ┌─────────────────┐ │
│  │ Task Planner│    │ Execution       │ │
│  │             │    │ Monitor         │ │
│  └─────────────┘    └─────────────────┘ │
│  ┌─────────────────────────────────────┐ │
│  │      Task Dispatcher                │ │
│  └─────────────────────────────────────┘ │
├─────────────────────────────────────────┤
│            Message Bus                  │
│    (Redis / AWS SQS / Custom)          │
├─────────────────────────────────────────┤
│  ┌───────┐ ┌───────┐ ┌─────────────────┐│
│  │ Agent │ │ Team  │ │ Team            ││
│  │       │ │       │ │ (Composition)   ││
│  └───────┘ └───────┘ └─────────────────┘│
└─────────────────────────────────────────┘
```

## Quick Start

### Installation

```bash
pip install -e .
```

### Basic Example

```python
import asyncio
from agentic_framework import AgenticFramework, TaskPriority

async def simple_handler(task):
    """Handle a simple task."""
    print(f"Processing: {task.title}")
    await asyncio.sleep(1)  # Simulate work
    return TaskResult.success_result({"processed": True})

async def main():
    async with AgenticFramework() as framework:
        # Create an agent with capabilities
        agent = framework.create_agent(
            name="DataProcessor",
            agent_type="processor",
            capabilities=["data_processing", "analysis"]
        )
        
        # Register task handler
        agent.register_task_handler("process_data", simple_handler)
        
        # Create a team
        team = framework.create_team(name="Processing Team")
        framework.add_agent_to_team(agent.id, team.id)
        
        # Create and execute a task
        task = framework.create_task(
            title="Process Customer Data",
            task_type="process_data",
            required_capabilities=["data_processing"],
            priority=TaskPriority.HIGH
        )
        
        # Execute task
        plan_id = await framework.execute_task(task, team.id)
        await framework.wait_for_completion(plan_id)
        
        print("Task completed!")

asyncio.run(main())
```

### Advanced Example with Team Composition

```python
import asyncio
from agentic_framework import AgenticFramework, TaskPriority

async def main():
    async with AgenticFramework() as framework:
        # Create specialized agents
        data_collector = framework.create_agent(
            name="DataCollector",
            agent_type="collector",
            capabilities=["data_access", "extraction"]
        )
        
        analyst = framework.create_agent(
            name="Analyst", 
            agent_type="analyst",
            capabilities=["analysis", "machine_learning"]
        )
        
        reporter = framework.create_agent(
            name="Reporter",
            agent_type="reporter", 
            capabilities=["reporting", "visualization"]
        )
        
        # Create team lead
        lead = framework.create_team_lead(
            name="AnalyticsLead",
            capabilities=["coordination", "planning"]
        )
        
        # Create specialized teams
        data_team = framework.create_team(name="Data Team")
        framework.add_agent_to_team(data_collector.id, data_team.id)
        
        analysis_team = framework.create_team(name="Analysis Team")
        framework.add_agent_to_team(lead.id, analysis_team.id, "lead")
        framework.add_agent_to_team(analyst.id, analysis_team.id)
        
        reporting_team = framework.create_team(name="Reporting Team")
        framework.add_agent_to_team(reporter.id, reporting_team.id)
        
        # Create super team with team composition
        super_team = framework.create_team(name="Analytics Division")
        framework.add_team_to_team(data_team.id, super_team.id, "data_specialist")
        framework.add_team_to_team(analysis_team.id, super_team.id, "analysis_specialist")
        framework.add_team_to_team(reporting_team.id, super_team.id, "reporting_specialist")
        
        # Execute complex task that will be automatically decomposed
        complex_task = framework.create_task(
            title="Q4 Business Intelligence Report",
            task_type="complex_analysis",
            required_capabilities=["data_access", "analysis", "reporting"],
            priority=TaskPriority.CRITICAL
        )
        
        plan_id = await framework.execute_task(complex_task, super_team.id)
        completed = await framework.wait_for_completion(plan_id, timeout=60)
        
        if completed:
            print("✅ Complex analysis completed!")
            status = framework.get_system_status()
            print(f"Completed {status['tasks']['completed']} tasks")

asyncio.run(main())
```

## Core Components

### Agents

Agents are the fundamental workers in the system:

- **Capabilities**: Define what an agent can do
- **Task Handlers**: Functions that process specific task types
- **Concurrent Tasks**: Configurable parallel processing capacity
- **Status Tracking**: Active, busy, error states

### Teams

Teams organize agents and provide orchestration:

- **Team Members**: Agents assigned to the team
- **Team Lead**: Special agent that can plan and coordinate
- **Team Composition**: Teams can be members of other teams
- **Load Balancing**: Automatic task distribution

### Tasks

Tasks represent work to be completed:

- **Task Types**: Categorize different kinds of work
- **Dependencies**: Tasks can depend on other tasks
- **Capabilities**: Required agent capabilities
- **Priority Levels**: Critical, high, normal, low
- **Automatic Decomposition**: Complex tasks broken into subtasks

### Message Bus

Enables distributed communication:

- **Redis**: Production-ready pub/sub messaging
- **AWS SQS**: Cloud-native queue system
- **Custom**: Implement your own message bus
- **Async**: Non-blocking message handling

## Development Setup

### Prerequisites

- Python 3.13+
- Redis (optional, for Redis message bus)

### Installation

```bash
# Clone the repository
git clone <repo-url>
cd agentic-framework

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install in development mode
pip install -e .

# Install development dependencies
pip install -e .[dev]
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=agentic_framework

# Run specific test file
pytest tests/unit/test_agent.py

# Run integration tests (requires Redis)
pytest tests/integration/
```

### Example Execution

```bash
# Start Redis (required for full example)
docker run -p 6379:6379 redis

# Run example
python -m agentic_framework.examples.example_team
```

## Configuration

### Message Bus Configuration

```python
from agentic_framework import AgenticFramework
from agentic_framework.messaging import RedisMessageBus

# Redis configuration
redis_bus = RedisMessageBus("redis://localhost:6379")
framework = AgenticFramework(message_bus=redis_bus)

# AWS SQS (implement SQSMessageBus)
# sqs_bus = SQSMessageBus(region="us-east-1")
# framework = AgenticFramework(message_bus=sqs_bus)
```

### Database Configuration

The framework includes SQLAlchemy models for persistence:

```python
from agentic_framework.storage.models import Base
from sqlalchemy import create_engine

# Create database
engine = create_engine("sqlite:///agents.db")
Base.metadata.create_all(engine)
```

## Architecture Decisions

### Clean Architecture

The framework follows clean architecture principles:

- **Domain Layer**: Core business logic (Agent, Team, Task)
- **Application Layer**: Use cases and orchestration
- **Infrastructure Layer**: Message bus, database, external services
- **Interface Layer**: Framework API and examples

### SOLID Principles

- **Single Responsibility**: Each class has one clear purpose
- **Open/Closed**: Extensible through interfaces and composition
- **Liskov Substitution**: Implementations are interchangeable
- **Interface Segregation**: Focused interfaces for specific needs
- **Dependency Inversion**: Depend on abstractions, not implementations

### Design Patterns

- **Repository Pattern**: Data access abstraction
- **Strategy Pattern**: Pluggable message bus implementations
- **Observer Pattern**: Event-driven message handling
- **Builder Pattern**: Fluent task creation API
- **Composition Pattern**: Hierarchical team structure

## Performance Considerations

### Scalability

- **Horizontal Scaling**: Add more agent instances
- **Message Bus**: Distribute across multiple Redis instances
- **Database**: Use read replicas and sharding
- **Monitoring**: Built-in metrics and health checks

### Optimization

- **Connection Pooling**: Efficient resource usage
- **Message Batching**: Reduce network overhead  
- **Async Processing**: Non-blocking operations
- **Capability Indexing**: Fast agent matching

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Follow the existing code style and patterns
4. Add tests for new functionality
5. Update documentation as needed
6. Submit a pull request

### Code Style

- Follow PEP 8 style guide
- Use type hints for all functions and methods
- Write comprehensive docstrings
- Maintain test coverage above 90%

### Testing Strategy

- **Unit Tests**: Test individual components in isolation
- **Integration Tests**: Test component interactions
- **End-to-End Tests**: Test complete workflows
- **Performance Tests**: Validate scalability claims

## License

MIT License - see LICENSE file for details.

## Support

- Documentation: [Coming Soon]
- Issues: GitHub Issues
- Discussions: GitHub Discussions
- Examples: See `examples/` directory

---

Built with ❤️ for the multi-agent future.