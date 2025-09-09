#!/usr/bin/env python3
"""
Example showing how to use the enhanced Agent class with capabilities as methods.
"""

import asyncio
import sys
from pathlib import Path

# Add the project root to path
sys.path.insert(0, str(Path(__file__).parent))

from agentic_framework import Agent, Task, TaskResult, InMemoryMessageBus


class FrontendDeveloper(Agent):
    """Frontend developer agent with capabilities as methods."""
    
    def __init__(self):
        super().__init__(id="frontend_developer", name="Frontend Dev", agent_type="developer")
        # Register capabilities - they must match method names
        self.add_capabilities(["create_website", "refine_styles"])
    
    async def create_website(self, task: Task) -> TaskResult:
        """Create a website based on task requirements."""
        design = task.input_data.get("design", "default")
        print(f"🌐 Creating {design} website...")
        
        # Simulate work
        await asyncio.sleep(0.5)
        
        return TaskResult.success_result(
            data={"website_url": f"https://mysite.com/{task.id}", "status": "created"},
            metadata={"creation_time": 0.5}
        )
    
    async def refine_styles(self, task: Task) -> TaskResult:
        """Refine website styles."""
        website_url = task.input_data.get("website_url")
        print(f"🎨 Refining styles for {website_url}...")
        
        await asyncio.sleep(0.3)
        
        return TaskResult.success_result(
            data={"optimized_styles": True, "performance_improvement": "25%"},
            metadata={"refinement_time": 0.3}
        )


async def main():
    """Demonstrate the enhanced Agent API."""
    print("🚀 Enhanced Agent Example")
    print("=" * 25)
    
    # Create agent with fluent API - capabilities are automatically validated
    agent = FrontendDeveloper()
    
    # Set up message bus
    message_bus = InMemoryMessageBus()
    await message_bus.connect()
    
    agent.set_message_bus(message_bus)
    await agent.start()
    
    print(f"✅ Agent created with capabilities: {[c for c in agent.capabilities]}")
    
    # Create tasks
    website_task = Task(
        title="Build Modern Website",
        input_data={"design": "modern", "theme": "dark"}
    )
    
    style_task = Task(
        title="Optimize Styles", 
        input_data={"website_url": "https://example.com"}
    )
    
    # Process tasks using capabilities - results automatically dispatched to bus
    print(f"\n📋 Processing Tasks:")
    await agent.process(website_task, capability="create_website")
    await agent.process(style_task, capability="refine_styles")
    
    # Show results
    print(f"\n📊 Results:")
    print(f"   Website Task: {website_task.result.success} - {website_task.result.data}")
    print(f"   Style Task: {style_task.result.success} - {style_task.result.data}")
    print(f"   Agent Stats: {agent.get_stats()}")
    
    # Cleanup
    await agent.stop()
    await message_bus.disconnect()
    
    print(f"\n🎉 Enhanced Agent example completed successfully!")


if __name__ == "__main__":
    asyncio.run(main())