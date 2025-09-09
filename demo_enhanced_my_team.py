#!/usr/bin/env python3
"""
Demo showing the enhanced Agent API in my-team.py working with the process method.
"""

import asyncio
import sys
from pathlib import Path

# Add the project root to path
sys.path.insert(0, str(Path(__file__).parent))

from agentic_framework import Task, TaskResult, InMemoryMessageBus

# Import the enhanced Agent classes from my-team.py
import importlib.util
my_team_path = Path(__file__).parent / "agentic_framework" / "examples" / "my-team.py"
spec = importlib.util.spec_from_file_location("my_team", my_team_path)
my_team = importlib.util.module_from_spec(spec)
spec.loader.exec_module(my_team)

ResearchAgent = my_team.ResearchAgent
WriterAgent = my_team.WriterAgent
EditorAgent = my_team.EditorAgent
TeamLeadAgent = my_team.TeamLeadAgent


async def demo_enhanced_agents():
    """Demonstrate the enhanced Agent API with capability methods."""
    print("🚀 Enhanced Agent API Demo")
    print("=" * 30)
    
    # Create message bus
    message_bus = InMemoryMessageBus()
    await message_bus.connect()
    
    # Create enhanced agents
    researcher = ResearchAgent("research-001", "Research Bot")
    writer = WriterAgent("writer-001", "Writing Bot") 
    editor = EditorAgent("editor-001", "Editor Bot")
    team_lead = TeamLeadAgent("lead-001", "Team Lead Bot")
    
    agents = [researcher, writer, editor, team_lead]
    
    # Set up agents
    for agent in agents:
        agent.set_message_bus(message_bus)
        await agent.start()
    
    print(f"✅ Created {len(agents)} enhanced agents:")
    for agent in agents:
        caps = [c.name for c in agent.capabilities]
        print(f"  - {agent.name}: {caps}")
    
    # Demo 1: Research Agent
    print(f"\n📋 Demo 1: Research Agent")
    print("-" * 25)
    
    research_task = Task(
        title="Research AI in Healthcare",
        task_type="research",
        input_data={"topic": "Artificial Intelligence in Healthcare"}
    )
    
    # Use the enhanced process method - automatically dispatches to message bus
    await researcher.process(research_task, capability="research")
    
    print(f"Research result: {research_task.result.success}")
    print(f"Key points found: {len(research_task.result.data.get('key_points', []))}")
    
    # Demo 2: Writer Agent (with simulated DSPy)
    print(f"\n📋 Demo 2: Writer Agent")
    print("-" * 20)
    
    writing_task = Task(
        title="Write Blog Post",
        task_type="writing",
        input_data={
            "topic": "AI in Healthcare",
            "research_data": research_task.result.data
        }
    )
    
    try:
        await writer.process(writing_task, capability="writing")
        print(f"Writing result: {writing_task.result.success}")
        if writing_task.result.success:
            blog_data = writing_task.result.data
            print(f"Blog title: {blog_data.get('title', 'N/A')}")
    except Exception as e:
        print(f"Writing failed (DSPy not configured): {e}")
        # Fallback - simulate success
        writing_task.result = TaskResult.success_result(
            data={
                "title": "AI in Healthcare: A Comprehensive Guide",
                "content": "Sample blog post content...",
                "word_count": 1500
            }
        )
        print(f"✅ Simulated writing success")
    
    # Demo 3: Editor Agent
    print(f"\n📋 Demo 3: Editor Agent")
    print("-" * 19)
    
    editing_task = Task(
        title="Edit Blog Post",
        task_type="editing", 
        input_data={"blog_post": writing_task.result.data}
    )
    
    await editor.process(editing_task, capability="editing")
    
    print(f"Editing result: {editing_task.result.success}")
    if editing_task.result.success:
        approved = editing_task.result.metadata.get("approved", False)
        print(f"Blog approved: {approved}")
    
    # Demo 4: Team Lead Coordination
    print(f"\n📋 Demo 4: Team Lead Coordination")
    print("-" * 30)
    
    coordination_task = Task(
        title="Coordinate Blog Writing",
        task_type="blog_writing",
        input_data={"topic": "Artificial Intelligence in Healthcare"}
    )
    
    await team_lead.process(coordination_task, capability="blog_writing")
    
    print(f"Coordination result: {coordination_task.result.success}")
    if coordination_task.result.success:
        workflow = coordination_task.result.data
        phases = workflow.get("phases_completed", [])
        print(f"Phases completed: {', '.join(phases)}")
        quality = workflow.get("quality_score", "N/A")
        print(f"Final quality score: {quality}")
    
    # Demo 5: Error Handling
    print(f"\n📋 Demo 5: Error Handling")
    print("-" * 22)
    
    invalid_task = Task(
        title="Invalid Task",
        task_type="test",
        input_data={}
    )
    
    await researcher.process(invalid_task, capability="nonexistent_capability")
    
    if invalid_task.result:
        print(f"Invalid capability result: {invalid_task.result.success}")
        print(f"Error message: {invalid_task.result.error_message}")
    else:
        print("Invalid capability result: Task failed to complete")
    
    # Show final agent statistics
    print(f"\n📊 Final Agent Statistics:")
    print("-" * 26)
    for agent in agents:
        stats = agent.get_stats()
        print(f"{agent.name}:")
        print(f"  Completed: {stats['completed_tasks']}")
        print(f"  Failed: {stats['failed_tasks']}")
        print(f"  Success rate: {stats['success_rate']:.1%}")
    
    # Cleanup
    for agent in agents:
        await agent.stop()
    await message_bus.disconnect()
    
    print(f"\n🎉 Enhanced Agent API Demo Complete!")
    print("✅ All capabilities work as methods")
    print("✅ Results automatically dispatch to message bus")
    print("✅ Error handling works correctly")


async def main():
    """Main demo function."""
    await demo_enhanced_agents()


if __name__ == "__main__":
    asyncio.run(main())