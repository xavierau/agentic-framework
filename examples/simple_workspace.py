#!/usr/bin/env python3
"""
Simple example demonstrating the new Workspace API with builder patterns.

This example shows how to:
1. Create a workspace with hierarchical structure
2. Build teams and agents using fluent interfaces
3. Execute tasks with automatic capability detection
4. Use simplified task creation
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path for direct execution
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent))

from agentic_framework import Workspace, Task, TaskResult

# Simple task handlers
async def data_handler(task):
    """Handle data collection tasks."""
    print(f"🔍 Collecting data: {task.title}")
    await asyncio.sleep(1)
    return TaskResult.success_result(
        data={"records": 100, "source": "database"},
        metadata={"collection_time": 1}
    )

async def analysis_handler(task):
    """Handle analysis tasks."""
    print(f"📊 Analyzing: {task.title}")
    await asyncio.sleep(1.5)
    return TaskResult.success_result(
        data={"insights": ["Growth up 15%", "User satisfaction improved"]},
        metadata={"analysis_time": 1.5}
    )

async def report_handler(task):
    """Handle reporting tasks."""
    print(f"📄 Creating report: {task.title}")
    await asyncio.sleep(0.5)
    return TaskResult.success_result(
        data={"report": "Monthly Analysis Report", "pages": 12},
        metadata={"report_time": 0.5}
    )

async def main():
    """Main example demonstrating simplified workspace API."""
    print("🚀 Simple Workspace Example")
    print("=" * 40)
    
    # Create workspace with clean API
    async with Workspace("MyCompany") as workspace:
        print("✅ Workspace started")
        
        # Build teams using fluent interface
        print("\n📋 Building Teams:")
        print("-" * 20)
        
        # Data team with lead and agent
        data_team = await workspace.team("Data Team") \
            .with_lead("Alice", ["coordination", "planning"]) \
            .with_agent("DataBot", ["data_collection", "data_access"]) \
            .build()
        
        # Register handlers
        alice = workspace.get_agent([member for member in data_team.members 
                                   if data_team.members[member].role == "lead"][0])
        databot = workspace.get_agent([member for member in data_team.members 
                                     if data_team.members[member].role == "member"][0])
        
        alice.register_task_handler("coordination", data_handler)  
        databot.register_task_handler("data_collection", data_handler)
        
        print(f"✅ Data team created: {data_team.name}")
        
        # Analytics team
        analytics_team = await workspace.team("Analytics Team") \
            .with_agent("Analyst", ["analysis", "ml"]) \
            .with_agent("Reporter", ["reporting", "visualization"]) \
            .max_concurrent(5) \
            .build()
        
        # Register handlers
        analyst = workspace.get_agent([member for member in analytics_team.members 
                                     if "analyst" in workspace.get_agent(member).name.lower()][0])
        reporter = workspace.get_agent([member for member in analytics_team.members 
                                      if "reporter" in workspace.get_agent(member).name.lower()][0])
        
        analyst.register_task_handler("analysis", analysis_handler)
        reporter.register_task_handler("reporting", report_handler)
        
        print(f"✅ Analytics team created: {analytics_team.name}")
        
        # Show workspace capabilities (auto-discovered from teams)
        print(f"\n🎯 Available capabilities: {sorted(workspace.capabilities)}")
        
        # Execute tasks using different methods
        print("\n⚡ Executing Tasks:")
        print("-" * 20)
        
        # Method 1: Simple task creation and team execution
        task1 = Task(title="Collect Q4 Sales Data", 
                    task_type="data_collection",
                    required_capabilities=["data_collection"])
        
        result1 = await data_team.execute(task1)
        print(f"Task 1 result: {result1.success} - {result1.data}")
        
        # Method 2: Task builder pattern
        task2 = Task.create("Monthly Revenue Analysis") \
            .of_type("analysis") \
            .requires("analysis") \
            .with_data(quarter="Q4", year=2024) \
            .build()
        
        result2 = await analytics_team.execute(task2)
        print(f"Task 2 result: {result2.success} - {result2.data}")
        
        # Method 3: Workspace auto-routing (finds right team automatically)
        task3 = Task(title="Generate Executive Summary", 
                    task_type="reporting"
                    # No capabilities specified - workspace will figure it out
                    )
        
        plan_id = await workspace.execute(task3)
        await workspace.wait_for_completion(plan_id, timeout=10)
        
        # Show final system status
        print(f"\n📊 Final Status:")
        print("-" * 16)
        status = workspace.get_system_status()
        print(f"Workspace: {status['workspace']}")
        print(f"Capabilities: {len(status['capabilities'])} total")
        print(f"Teams: {status['teams']['total']}")
        print(f"Agents: {status['agents']['total']}")
        print(f"Completed tasks: {status['tasks']['completed']}")
        
        print("\n🎉 Simple workspace example completed!")

if __name__ == "__main__":
    asyncio.run(main())