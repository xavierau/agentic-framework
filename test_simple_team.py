#!/usr/bin/env python3
"""
Simple test to verify team messaging works with InMemoryMessageBus.
"""
import asyncio
import sys
from pathlib import Path

# Add the project root to path
sys.path.insert(0, str(Path(__file__).parent))

from agentic_framework import AgenticFramework, InMemoryMessageBus, Task, TaskPriority

async def simple_handler(task):
    """Simple task handler for testing."""
    print(f"✅ Task handler executed: {task.title}")
    await asyncio.sleep(1)  # Simulate work
    # Return proper TaskResult
    from agentic_framework import TaskResult
    return TaskResult.success_result(
        data={"processed": f"Processed: {task.title}"}
    )

async def test_simple_team():
    """Test a simple team workflow with InMemoryMessageBus."""
    print("🧪 Testing Simple Team Workflow")
    print("=" * 35)
    
    try:
        framework = AgenticFramework(message_bus=InMemoryMessageBus())
        
        async with framework:
            print("✅ Framework started with InMemoryMessageBus")
            
            # Create a simple agent
            agent = await framework.create_agent(
                name="TestAgent",
                agent_type="worker", 
                capabilities=["test"]
            )
            agent.register_task_handler("test", simple_handler)
            print(f"✅ Agent created: {agent.name}")
            
            # Create a simple team
            team = framework.create_team(
                name="Test Team",
                description="Simple test team"
            )
            await framework.add_agent_to_team(agent.id, team.id, "member")
            print(f"✅ Team created: {team.name}")
            
            # Give the team time to fully start
            await asyncio.sleep(0.5)
            
            # Create and execute a simple task
            task = framework.create_task(
                title="Simple Test Task",
                task_type="test",
                description="A simple test task",
                input_data={"message": "Hello from test!"},
                required_capabilities=["test"],
                priority=TaskPriority.HIGH
            )
            print(f"✅ Task created: {task.title}")
            
            # Execute the task
            print("🚀 Executing task...")
            plan_id = await framework.execute_task(task, team.id)
            print(f"✅ Execution plan created: {plan_id}")
            
            # Wait for completion with longer timeout
            print("⏳ Waiting for task completion...")
            # Give a short wait for the task to actually complete
            await asyncio.sleep(2)
            completed = await framework.wait_for_completion(plan_id, timeout=3)
            
            if completed:
                print("🎉 Task completed successfully!")
                
                # Get final status
                status = framework.get_system_status()
                print(f"📊 Final Status:")
                print(f"   Tasks completed: {status['tasks']['completed']}")
                print(f"   Tasks failed: {status['tasks']['failed']}")
                return True
            else:
                print("⚠️ Task did not complete within timeout")
                
                # Debug info
                status = framework.get_system_status()
                print(f"📊 Debug Status:")
                print(f"   Tasks completed: {status['tasks']['completed']}")
                print(f"   Tasks failed: {status['tasks']['failed']}")
                print(f"   Tasks in progress: {status['tasks']['in_progress']}")
                
                # Check message bus stats
                if hasattr(framework.message_bus, 'get_stats'):
                    bus_stats = framework.message_bus.get_stats()
                    print(f"📡 Message Bus Stats:")
                    print(f"   Channels: {bus_stats['channels']}")
                    print(f"   Handlers: {bus_stats['total_handlers']}")
                    print(f"   Queue Size: {bus_stats['queue_size']}")
                    print(f"   Channel Details: {bus_stats['channel_details']}")
                
                return False
                
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_simple_team())
    if success:
        print("\n🎉 Simple team test PASSED!")
    else:
        print("\n💥 Simple team test FAILED!")
        sys.exit(1)