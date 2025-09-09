#!/usr/bin/env python3
"""
Test the enhanced Agent class with internal capability processing.
"""

import asyncio
import sys
from pathlib import Path

# Add the project root to path
sys.path.insert(0, str(Path(__file__).parent))

from agentic_framework import Agent, Task, TaskResult, InMemoryMessageBus, AgenticFramework


class FrontendDeveloper(Agent):
    """Example agent that implements capabilities as methods."""
    
    def __init__(self):
        super().__init__(id="frontend_developer", name="Frontend Developer", agent_type="developer")
        # Register capabilities that match method names
        self.add_capabilities(["create_website", "refine_styles"])
    
    async def create_website(self, task: Task) -> TaskResult:
        """Capability method to create a website."""
        design = task.input_data.get("design", "default")
        theme = task.input_data.get("theme", "light")
        
        print(f"🌐 Creating website with design: {design}, theme: {theme}")
        
        # Simulate work
        await asyncio.sleep(1)
        
        website_data = {
            "url": f"https://example.com/{task.id}",
            "design": design,
            "theme": theme,
            "components": ["header", "main", "footer"],
            "status": "created"
        }
        
        print(f"✅ Website created successfully!")
        return TaskResult.success_result(
            data=website_data,
            metadata={"creation_time": 1.0}
        )
    
    async def refine_styles(self, task: Task) -> TaskResult:
        """Capability method to refine styles."""
        styles = task.input_data.get("styles", {})
        website_url = task.input_data.get("website_url", "")
        
        print(f"🎨 Refining styles for {website_url}")
        
        # Simulate work
        await asyncio.sleep(0.5)
        
        refined_styles = {
            **styles,
            "optimized": True,
            "performance_score": 95,
            "accessibility_score": 90
        }
        
        print(f"✅ Styles refined successfully!")
        return TaskResult.success_result(
            data={"refined_styles": refined_styles},
            metadata={"refinement_time": 0.5}
        )


class BackendDeveloper(Agent):
    """Example backend developer agent."""
    
    def __init__(self):
        super().__init__(id="backend_developer", name="Backend Developer", agent_type="developer")
        self.add_capabilities(["create_api", "optimize_database"])
    
    def create_api(self, task: Task) -> TaskResult:
        """Capability method to create an API (sync example)."""
        endpoints = task.input_data.get("endpoints", [])
        
        print(f"🔧 Creating API with endpoints: {endpoints}")
        
        api_data = {
            "api_version": "v1",
            "endpoints": endpoints,
            "documentation_url": f"https://api.example.com/{task.id}/docs",
            "status": "created"
        }
        
        print(f"✅ API created successfully!")
        return TaskResult.success_result(
            data=api_data,
            metadata={"creation_method": "sync"}
        )
    
    async def optimize_database(self, task: Task) -> TaskResult:
        """Capability method to optimize database."""
        tables = task.input_data.get("tables", [])
        
        print(f"🗄️ Optimizing database tables: {tables}")
        await asyncio.sleep(0.8)
        
        optimization_data = {
            "optimized_tables": tables,
            "performance_improvement": "35%",
            "query_time_reduction": "50ms",
            "status": "optimized"
        }
        
        print(f"✅ Database optimized successfully!")
        return TaskResult.success_result(
            data=optimization_data,
            metadata={"optimization_time": 0.8}
        )


async def test_capability_validation():
    """Test that capability validation works correctly."""
    print("\n🧪 Testing Capability Validation")
    print("=" * 40)
    
    class IncompleteAgent(Agent):
        def __init__(self):
            super().__init__(id="incomplete", name="Incomplete Agent", agent_type="test")
    
    agent = IncompleteAgent()
    
    # This should raise an error because the method doesn't exist
    try:
        agent.add_capabilities(["missing_method"])
        print("❌ ERROR: Should have raised ValueError")
        return False
    except ValueError as e:
        print(f"✅ Correctly caught error: {e}")
        return True


async def test_enhanced_agent():
    """Test the enhanced agent functionality."""
    print("\n🧪 Testing Enhanced Agent Functionality")
    print("=" * 45)
    
    # Test message collection
    messages_received = []
    
    async def message_handler(message):
        messages_received.append(message)
        print(f"📨 Received message: {message.message_type}")
    
    # Create message bus and framework
    message_bus = InMemoryMessageBus()
    framework = AgenticFramework(message_bus=message_bus)
    
    async with framework:
        # Create agents
        frontend_agent = FrontendDeveloper()
        backend_agent = BackendDeveloper()
        
        # Set message bus
        frontend_agent.set_message_bus(message_bus)
        backend_agent.set_message_bus(message_bus)
        
        # Subscribe to task-specific channels dynamically
        task_channels = []
        
        # Start agents
        await frontend_agent.start()
        await backend_agent.start()
        
        print(f"✅ Agents started successfully!")
        
        # Test 1: Frontend agent creating a website
        print(f"\n1️⃣ Testing website creation:")
        website_task = Task(
            title="Create Modern Website",
            task_type="web_development",
            input_data={
                "design": "modern",
                "theme": "dark"
            }
        )
        
        # Subscribe to this task's channel
        await message_bus.subscribe(f"task.{website_task.id}", message_handler)
        task_channels.append(f"task.{website_task.id}")
        
        # Process with capability - this should auto-dispatch to message bus
        await frontend_agent.process(website_task, capability="create_website")
        
        # Test 2: Backend agent creating API (sync method)
        print(f"\n2️⃣ Testing API creation:")
        api_task = Task(
            title="Create REST API",
            task_type="backend_development", 
            input_data={
                "endpoints": ["/users", "/posts", "/comments"]
            }
        )
        
        # Subscribe to this task's channel
        await message_bus.subscribe(f"task.{api_task.id}", message_handler)
        task_channels.append(f"task.{api_task.id}")
        
        await backend_agent.process(api_task, capability="create_api")
        
        # Test 3: Frontend agent refining styles
        print(f"\n3️⃣ Testing style refinement:")
        style_task = Task(
            title="Refine Website Styles",
            task_type="styling",
            input_data={
                "website_url": website_task.result.data.get("url"),
                "styles": {"color": "dark", "font": "modern"}
            }
        )
        
        # Subscribe to this task's channel
        await message_bus.subscribe(f"task.{style_task.id}", message_handler)
        task_channels.append(f"task.{style_task.id}")
        
        await frontend_agent.process(style_task, capability="refine_styles")
        
        # Test 4: Backend database optimization
        print(f"\n4️⃣ Testing database optimization:")
        db_task = Task(
            title="Optimize Database",
            task_type="database",
            input_data={
                "tables": ["users", "posts", "comments"]
            }
        )
        
        # Subscribe to this task's channel
        await message_bus.subscribe(f"task.{db_task.id}", message_handler)
        task_channels.append(f"task.{db_task.id}")
        
        await backend_agent.process(db_task, capability="optimize_database")
        
        # Test 5: Error handling - invalid capability
        print(f"\n5️⃣ Testing error handling:")
        invalid_task = Task(
            title="Invalid Task",
            task_type="test",
            input_data={}
        )
        
        # Subscribe to this task's channel
        await message_bus.subscribe(f"task.{invalid_task.id}", message_handler)
        task_channels.append(f"task.{invalid_task.id}")
        
        await frontend_agent.process(invalid_task, capability="nonexistent_capability")
        
        # Give time for messages to be processed
        await asyncio.sleep(0.2)
        
        # Stop agents
        await frontend_agent.stop()
        await backend_agent.stop()
        
        # Clean up subscriptions
        for channel in task_channels:
            await message_bus.unsubscribe(channel, message_handler)
        
        # Analyze results
        print(f"\n📊 Test Results:")
        print(f"   Frontend Agent Stats: {frontend_agent.get_stats()}")
        print(f"   Backend Agent Stats: {backend_agent.get_stats()}")
        print(f"   Messages Received: {len(messages_received)}")
        
        # Check that we received the expected number of messages
        expected_messages = 5  # 4 successful + 1 failed
        if len(messages_received) >= expected_messages:
            print(f"✅ All expected messages received!")
            return True
        else:
            print(f"❌ Expected at least {expected_messages} messages, got {len(messages_received)}")
            return False


async def main():
    """Main test function."""
    print("🚀 Testing Enhanced Agent Class")
    print("=" * 35)
    
    # Test capability validation
    validation_passed = await test_capability_validation()
    
    # Test enhanced functionality  
    functionality_passed = await test_enhanced_agent()
    
    # Overall results
    print(f"\n🎯 Overall Test Results:")
    print(f"   Capability Validation: {'✅ PASSED' if validation_passed else '❌ FAILED'}")
    print(f"   Enhanced Functionality: {'✅ PASSED' if functionality_passed else '❌ FAILED'}")
    
    if validation_passed and functionality_passed:
        print(f"\n🎉 All tests PASSED!")
        print(f"💡 Enhanced Agent class is working correctly!")
        return True
    else:
        print(f"\n💥 Some tests FAILED!")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    if not success:
        sys.exit(1)