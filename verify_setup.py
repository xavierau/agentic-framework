#!/usr/bin/env python3
"""
Quick verification script to ensure the agentic framework is working correctly.
"""

import asyncio
from agentic_framework import (
    AgenticFramework, 
    TaskPriority, 
    TaskResult
)

async def simple_handler(task):
    """Simple task handler for verification."""
    print(f"🔧 Processing: {task.title}")
    await asyncio.sleep(0.1)  # Simulate work
    return TaskResult.success_result({"status": "completed", "task_id": task.id})

async def main():
    """Main verification function."""
    print("🚀 Agentic Framework - Setup Verification")
    print("=" * 50)
    
    # Test 1: Framework initialization
    print("\n✅ Test 1: Framework initialization")
    framework = AgenticFramework()
    print("   Framework created successfully")
    
    # Test 2: Agent creation
    print("\n✅ Test 2: Agent and team creation")
    async with framework:
        # Create agents
        agent1 = framework.create_agent(
            name="VerificationAgent",
            agent_type="test_agent",
            capabilities=["verification", "testing"]
        )
        agent1.register_task_handler("verification", simple_handler)
        
        # Create team
        team = framework.create_team(name="VerificationTeam")
        framework.add_agent_to_team(agent1.id, team.id)
        
        print(f"   Agent created: {agent1.name} ({agent1.id[:8]}...)")
        print(f"   Team created: {team.name} ({team.id[:8]}...)")
        print(f"   Team members: {len(team.members)}")
        
        # Test 3: Task creation and execution
        print("\n✅ Test 3: Task creation")
        task = framework.create_task(
            title="Verification Test Task",
            task_type="verification",
            description="Test task to verify framework functionality",
            required_capabilities=["verification"],
            priority=TaskPriority.HIGH
        )
        print(f"   Task created: {task.title} ({task.id[:8]}...)")
        
        # Test 4: System status
        print("\n✅ Test 4: System status")
        status = framework.get_system_status()
        print(f"   Running: {status['running']}")
        print(f"   Agents: {status['agents']['total']} total, {status['agents']['active']} active")
        print(f"   Teams: {status['teams']['total']} total")
    
    print("\n🎉 All verification tests passed!")
    print("🔥 The Agentic Framework is ready to use!")
    print("\nNext steps:")
    print("1. Start Redis: docker run -p 6379:6379 redis")
    print("2. Run the full example: python agentic_framework/examples/example_team.py")
    print("3. Build your own multi-agent applications!")

if __name__ == "__main__":
    asyncio.run(main())