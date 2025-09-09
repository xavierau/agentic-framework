"""Command-line interface for the stateless agentic framework."""

import asyncio
import sys
import json
from typing import Dict, Any, Optional, List
from uuid import uuid4
import click
import structlog

from .messaging.hybrid_bus import HybridMessageBus
from .events.event_types import TaskCreated, AgentCreated, TeamCreated
from .planning.workflow import WorkflowStore, WorkflowDefinition
from .workers.spawner import WorkerSpawner


# Configure logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="ISO"),
        structlog.dev.ConsoleRenderer()
    ],
    wrapper_class=structlog.make_filtering_bound_logger(20),  # INFO level
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True
)

logger = structlog.get_logger()


@click.group()
@click.option('--sqlite-path', default='events.db', help='Path to SQLite event store')
@click.option('--redis-url', default='redis://localhost:6379', help='Redis connection URL')
@click.option('--log-level', default='INFO', help='Logging level')
@click.pass_context
def cli(ctx, sqlite_path, redis_url, log_level):
    """Stateless Agentic Framework CLI."""
    ctx.ensure_object(dict)
    ctx.obj['sqlite_path'] = sqlite_path
    ctx.obj['redis_url'] = redis_url
    ctx.obj['log_level'] = log_level


@cli.command()
@click.option('--task-type', required=True, help='Type of task to create')
@click.option('--title', required=True, help='Task title')
@click.option('--priority', default=2, help='Task priority (1=low, 2=normal, 3=high, 4=critical)')
@click.option('--capabilities', help='Required capabilities (comma-separated)')
@click.option('--workflow', help='Specific workflow ID to use')
@click.option('--input-data', help='Input data as JSON string')
@click.pass_context
async def create_task(ctx, task_type, title, priority, capabilities, workflow, input_data):
    """Create and dispatch a new task."""
    
    # Parse input data
    parsed_input = {}
    if input_data:
        try:
            parsed_input = json.loads(input_data)
        except json.JSONDecodeError:
            click.echo(f"Error: Invalid JSON in input-data: {input_data}")
            sys.exit(1)
    
    # Parse capabilities
    required_capabilities = []
    if capabilities:
        required_capabilities = [cap.strip() for cap in capabilities.split(',')]
    
    # Create task ID
    task_id = str(uuid4())
    
    try:
        # Initialize message bus
        bus = HybridMessageBus(
            sqlite_path=ctx.obj['sqlite_path'],
            redis_url=ctx.obj['redis_url']
        )
        await bus.connect()
        
        # Create task event
        task_event = TaskCreated(
            task_id=task_id,
            title=title,
            task_type=task_type,
            priority=priority,
            required_capabilities=required_capabilities,
            input_data=parsed_input,
            workflow_id=workflow
        )
        
        # Dispatch to event store & message bus
        sequence_number = await bus.dispatch_event(task_event)
        
        await bus.disconnect()
        
        click.echo(f"Task created successfully!")
        click.echo(f"Task ID: {task_id}")
        click.echo(f"Sequence Number: {sequence_number}")
        click.echo(f"Task will be processed by available workers.")
        
    except Exception as e:
        logger.error("Failed to create task", error=str(e))
        click.echo(f"Error creating task: {str(e)}")
        sys.exit(1)


@cli.command()
@click.option('--name', required=True, help='Agent name')
@click.option('--agent-type', required=True, help='Agent type')
@click.option('--capabilities', help='Agent capabilities (comma-separated)')
@click.pass_context
async def create_agent(ctx, name, agent_type, capabilities):
    """Create a new agent."""
    
    # Parse capabilities
    agent_capabilities = []
    if capabilities:
        agent_capabilities = [cap.strip() for cap in capabilities.split(',')]
    
    agent_id = str(uuid4())
    
    try:
        # Initialize message bus
        bus = HybridMessageBus(
            sqlite_path=ctx.obj['sqlite_path'],
            redis_url=ctx.obj['redis_url']
        )
        await bus.connect()
        
        # Create agent event
        agent_event = AgentCreated(
            agent_id=agent_id,
            name=name,
            agent_type=agent_type,
            capabilities=agent_capabilities
        )
        
        # Dispatch to event store
        sequence_number = await bus.dispatch_event(agent_event)
        
        await bus.disconnect()
        
        click.echo(f"Agent created successfully!")
        click.echo(f"Agent ID: {agent_id}")
        click.echo(f"Name: {name}")
        click.echo(f"Type: {agent_type}")
        click.echo(f"Capabilities: {', '.join(agent_capabilities)}")
        click.echo(f"Sequence Number: {sequence_number}")
        
    except Exception as e:
        logger.error("Failed to create agent", error=str(e))
        click.echo(f"Error creating agent: {str(e)}")
        sys.exit(1)


@cli.command()
@click.option('--name', required=True, help='Team name')
@click.option('--description', help='Team description')
@click.pass_context
async def create_team(ctx, name, description):
    """Create a new team."""
    
    team_id = str(uuid4())
    
    try:
        # Initialize message bus
        bus = HybridMessageBus(
            sqlite_path=ctx.obj['sqlite_path'],
            redis_url=ctx.obj['redis_url']
        )
        await bus.connect()
        
        # Create team event
        team_event = TeamCreated(
            team_id=team_id,
            name=name,
            description=description
        )
        
        # Dispatch to event store
        sequence_number = await bus.dispatch_event(team_event)
        
        await bus.disconnect()
        
        click.echo(f"Team created successfully!")
        click.echo(f"Team ID: {team_id}")
        click.echo(f"Name: {name}")
        if description:
            click.echo(f"Description: {description}")
        click.echo(f"Sequence Number: {sequence_number}")
        
    except Exception as e:
        logger.error("Failed to create team", error=str(e))
        click.echo(f"Error creating team: {str(e)}")
        sys.exit(1)


@cli.command()
@click.option('--from-sequence', default=0, help='Starting sequence number')
@click.option('--to-sequence', help='Ending sequence number')
@click.option('--event-types', help='Event types to replay (comma-separated)')
@click.pass_context
async def replay_events(ctx, from_sequence, to_sequence, event_types):
    """Replay events from SQLite to Redis."""
    
    # Parse event types
    types_filter = None
    if event_types:
        types_filter = [t.strip() for t in event_types.split(',')]
    
    try:
        # Initialize message bus
        bus = HybridMessageBus(
            sqlite_path=ctx.obj['sqlite_path'],
            redis_url=ctx.obj['redis_url']
        )
        await bus.connect()
        
        click.echo(f"Starting event replay...")
        click.echo(f"From sequence: {from_sequence}")
        if to_sequence:
            click.echo(f"To sequence: {to_sequence}")
        if types_filter:
            click.echo(f"Event types: {', '.join(types_filter)}")
        
        # Replay events
        replayed_count = await bus.replay_events(
            from_sequence=from_sequence,
            to_sequence=int(to_sequence) if to_sequence else None,
            event_types=types_filter
        )
        
        await bus.disconnect()
        
        click.echo(f"Event replay completed!")
        click.echo(f"Events replayed: {replayed_count}")
        
    except Exception as e:
        logger.error("Failed to replay events", error=str(e))
        click.echo(f"Error replaying events: {str(e)}")
        sys.exit(1)


@cli.command()
@click.pass_context
async def status(ctx):
    """Show system status."""
    
    try:
        # Initialize message bus
        bus = HybridMessageBus(
            sqlite_path=ctx.obj['sqlite_path'],
            redis_url=ctx.obj['redis_url']
        )
        await bus.connect()
        
        # Get status
        system_status = await bus.get_status()
        queue_length = await bus.get_work_queue_length()
        
        await bus.disconnect()
        
        click.echo("=== System Status ===")
        click.echo(f"SQLite Database: {system_status['sqlite']['database_path']}")
        click.echo(f"Next Sequence: {system_status['sqlite']['next_sequence']}")
        click.echo(f"Redis URL: {system_status['redis']['url']}")
        click.echo(f"Redis Status: {system_status['redis']['status']}")
        click.echo(f"Work Queue Length: {queue_length}")
        
        if system_status.get('replay'):
            click.echo(f"Replay Active: {system_status['replay']['active']}")
            click.echo(f"Last Replayed: {system_status['replay']['last_replayed_sequence']}")
        
    except Exception as e:
        logger.error("Failed to get status", error=str(e))
        click.echo(f"Error getting status: {str(e)}")
        sys.exit(1)


@cli.command()
@click.option('--worker-type', default='all', help='Type of workers to spawn (all, planner, executor)')
@click.option('--count', default=1, help='Number of workers to spawn')
@click.option('--detach', is_flag=True, help='Run workers in detached mode')
@click.pass_context
async def spawn_workers(ctx, worker_type, count, detach):
    """Spawn worker processes."""
    
    try:
        spawner = WorkerSpawner(
            sqlite_path=ctx.obj['sqlite_path'],
            redis_url=ctx.obj['redis_url']
        )
        
        click.echo(f"Spawning {count} {worker_type} worker(s)...")
        
        worker_ids = []
        for i in range(count):
            worker_id = await spawner.spawn_worker(worker_type, detach=detach)
            worker_ids.append(worker_id)
            click.echo(f"Spawned worker: {worker_id}")
        
        if not detach:
            click.echo("Workers running. Press Ctrl+C to stop...")
            try:
                # Wait for workers
                await spawner.wait_for_workers(worker_ids)
            except KeyboardInterrupt:
                click.echo("Stopping workers...")
                await spawner.stop_workers(worker_ids)
        else:
            click.echo("Workers running in background.")
        
    except Exception as e:
        logger.error("Failed to spawn workers", error=str(e))
        click.echo(f"Error spawning workers: {str(e)}")
        sys.exit(1)


@cli.command()
@click.option('--workflow-file', required=True, help='Path to workflow definition JSON file')
@click.pass_context
async def load_workflow(ctx, workflow_file):
    """Load a workflow definition from a JSON file."""
    
    try:
        # Read workflow file
        with open(workflow_file, 'r') as f:
            workflow_data = json.load(f)
        
        # Create workflow definition
        workflow = WorkflowDefinition(**workflow_data)
        
        # Validate workflow
        errors = workflow.validate_workflow()
        if errors:
            click.echo("Workflow validation failed:")
            for error in errors:
                click.echo(f"  - {error}")
            sys.exit(1)
        
        # Save to workflow store
        store = WorkflowStore(ctx.obj['sqlite_path'])
        store.save_workflow(workflow)
        
        click.echo(f"Workflow loaded successfully!")
        click.echo(f"Workflow ID: {workflow.id}")
        click.echo(f"Name: {workflow.name}")
        click.echo(f"Version: {workflow.version}")
        click.echo(f"Steps: {len(workflow.steps)}")
        
    except Exception as e:
        logger.error("Failed to load workflow", error=str(e))
        click.echo(f"Error loading workflow: {str(e)}")
        sys.exit(1)


@cli.command()
@click.pass_context
async def list_workflows(ctx):
    """List all available workflows."""
    
    try:
        store = WorkflowStore(ctx.obj['sqlite_path'])
        workflows = store.list_workflows()
        
        if not workflows:
            click.echo("No workflows found.")
            return
        
        click.echo("=== Available Workflows ===")
        for workflow in workflows:
            click.echo(f"ID: {workflow.id}")
            click.echo(f"Name: {workflow.name}")
            click.echo(f"Version: {workflow.version}")
            click.echo(f"Steps: {len(workflow.steps)}")
            click.echo(f"Active: {workflow.is_active}")
            click.echo("---")
        
    except Exception as e:
        logger.error("Failed to list workflows", error=str(e))
        click.echo(f"Error listing workflows: {str(e)}")
        sys.exit(1)


def main():
    """Main entry point for the CLI."""
    
    # Convert async commands to sync
    original_commands = {}
    for name, command in cli.commands.items():
        original_commands[name] = command.callback
        
        # Wrap async commands
        if asyncio.iscoroutinefunction(command.callback):
            def make_sync_wrapper(async_func):
                def sync_wrapper(*args, **kwargs):
                    return asyncio.run(async_func(*args, **kwargs))
                sync_wrapper.__name__ = async_func.__name__
                sync_wrapper.__doc__ = async_func.__doc__
                return sync_wrapper
            
            command.callback = make_sync_wrapper(command.callback)
    
    cli()


if __name__ == '__main__':
    main()