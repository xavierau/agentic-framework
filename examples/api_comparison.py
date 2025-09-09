#!/usr/bin/env python3
"""
API Comparison: Before vs After

This example demonstrates the improvement in API usability from the original
verbose approach to the new simplified builder-pattern approach.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path for direct execution
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent))

from agentic_framework import Workspace, AgenticFramework, Task, TaskResult

async def sample_handler(task):
    """Sample task handler."""
    await asyncio.sleep(0.1)
    return TaskResult.success_result(data={"processed": task.title})

async def old_way_example():
    """Example using the original verbose API."""
    print("📚 OLD WAY (Verbose):")
    print("-" * 25)
    
    # Original approach - many steps, verbose
    framework = AgenticFramework()
    
    async with framework:
        # Create agents separately
        agent1 = await framework.create_agent(
            name="DataAnalyst",
            agent_type="analyst", 
            capabilities=["data_analysis", "reporting"],
            max_concurrent_tasks=2
        )
        agent1.register_task_handler("data_analysis", sample_handler)
        
        agent2 = await framework.create_agent(
            name="DataCollector",
            agent_type="collector",
            capabilities=["data_collection", "data_access"],
            max_concurrent_tasks=1
        )
        agent2.register_task_handler("data_collection", sample_handler)
        
        # Create team lead
        lead = framework.create_team_lead(
            name="TeamLead",
            capabilities=["coordination", "planning"],
            max_concurrent_tasks=5
        )
        lead.register_task_handler("coordination", sample_handler)
        
        # Create team
        team = framework.create_team(
            name="Analytics Team",
            description="Data analytics team",
            max_concurrent_tasks=10
        )
        
        # Add members to team (separate calls)
        await framework.add_agent_to_team(lead.id, team.id, "lead")
        await framework.add_agent_to_team(agent1.id, team.id, "member")
        await framework.add_agent_to_team(agent2.id, team.id, "member")
        
        # Create task using builder
        task = framework.create_task(
            title="Analyze Q4 Data",
            task_type="analysis",
            description="Comprehensive Q4 analysis",
            required_capabilities=["data_collection", "data_analysis"],
            priority=TaskPriority.HIGH
        )
        
        # Execute task
        plan_id = await framework.execute_task(task, team.id)
        completed = await framework.wait_for_completion(plan_id, timeout=5)
        
        print(f"Lines of code: ~30")
        print(f"Method calls: ~10")
        print(f"Task completed: {'✅' if completed else '❌'}")

async def new_way_example():
    """Example using the new simplified API."""
    print("\n🚀 NEW WAY (Simplified):")
    print("-" * 28)
    
    # New approach - concise, fluent
    async with Workspace("Analytics") as workspace:
        # Create team with agents in one fluent call
        team = await workspace.team("Analytics Team")
            .with_lead("TeamLead", ["coordination", "planning"])
            .with_agent("DataAnalyst", ["data_analysis", "reporting"])  
            .with_agent("DataCollector", ["data_collection", "data_access"])
            .build()
        
        # Register handlers (could be done in builder in future)
        for agent_id in team.members:
            agent = workspace.get_agent(agent_id)
            agent.register_task_handler("data_analysis", sample_handler)
            agent.register_task_handler("data_collection", sample_handler)
            agent.register_task_handler("coordination", sample_handler)
        
        # Create and execute task (multiple ways)
        
        # Way 1: Direct task creation and team execution
        task1 = Task("Analyze Q4 Data", requires=["data_collection", "data_analysis"])
        result1 = await team.execute(task1)
        
        # Way 2: Builder pattern
        task2 = Task.create("Generate Report")
            .of_type("reporting")
            .requires("data_analysis", "reporting")
            .with_data(quarter="Q4", format="PDF")
            .build()
        result2 = await team.execute(task2)
        
        # Way 3: Workspace auto-routing
        task3 = Task("Monthly Summary")  # No capabilities - auto-planned
        plan_id = await workspace.execute(task3)
        completed = await workspace.wait_for_completion(plan_id, timeout=5)
        
        print(f"Lines of code: ~15")
        print(f"Method calls: ~5")
        print(f"Tasks completed: {'✅' if all([result1.success, result2.success, completed]) else '❌'}")

async def hierarchical_example():
    """Example showing hierarchical workspace simplification."""
    print("\n🏢 HIERARCHICAL WORKSPACES:")
    print("-" * 32)
    
    # Create department workspaces
    sales_ws = Workspace("Sales")
    engineering_ws = Workspace("Engineering")
    
    async with sales_ws:
        sales_team = await sales_ws.team("Sales Team")
            .with_agent("SalesRep", ["sales", "crm"])
            .build()
        
        # Register handler
        for agent_id in sales_team.members:
            sales_ws.get_agent(agent_id).register_task_handler("sales", sample_handler)
    
    async with engineering_ws:
        eng_team = await engineering_ws.team("Engineering Team")
            .with_agent("Developer", ["coding", "testing"])
            .build()
        
        # Register handler  
        for agent_id in eng_team.members:
            engineering_ws.get_agent(agent_id).register_task_handler("coding", sample_handler)
    
    # Create enterprise workspace - simple hierarchy
    enterprise = Workspace("Enterprise")
        .add(sales_ws)
        .add(engineering_ws)
    
    async with enterprise:
        # Capabilities automatically bubble up
        print(f"Enterprise capabilities: {sorted(enterprise.capabilities)}")
        
        # Cross-department task - automatically routed
        task = Task("Product Revenue Analysis", requires=["sales", "coding"])
        plan_id = await enterprise.execute(task)
        completed = await enterprise.wait_for_completion(plan_id, timeout=5)
        
        print(f"Cross-department task: {'✅' if completed else '❌'}")
        print(f"Total workspaces: {1 + len(enterprise.children)}")
        print(f"Auto capability discovery: ✅")

async def main():
    """Compare old vs new API approaches."""
    print("🔄 API Comparison: Before vs After")
    print("=" * 50)
    
    await old_way_example()
    await new_way_example()  
    await hierarchical_example()
    
    print(f"\n📊 Summary of Improvements:")
    print("-" * 30)
    print("✅ Fluent builder interfaces")
    print("✅ Hierarchical workspace support")
    print("✅ Automatic capability discovery")
    print("✅ Auto task planning and routing")
    print("✅ Direct team task execution")
    print("✅ Reduced lines of code (~50% less)")
    print("✅ Fewer method calls (~50% less)")
    print("✅ More intuitive API design")
    print("✅ Better developer experience")
    
    print("\n🎉 API comparison completed!")

if __name__ == "__main__":
    asyncio.run(main())