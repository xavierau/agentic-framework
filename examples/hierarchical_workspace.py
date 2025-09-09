#!/usr/bin/env python3
"""
Hierarchical workspace example demonstrating multi-level organization.

This example shows:
1. Enterprise workspace containing department workspaces
2. Automatic capability bubbling from child to parent
3. Cross-department task routing
4. Team composition across workspace boundaries
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path for direct execution
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent))

from agentic_framework import Workspace, Task, TaskResult

# Department-specific handlers
async def sales_handler(task):
    """Handle sales tasks."""
    print(f"💰 Sales processing: {task.title}")
    await asyncio.sleep(1)
    return TaskResult.success_result(
        data={"revenue": 150000, "deals": 25},
        metadata={"department": "sales"}
    )

async def engineering_handler(task):
    """Handle engineering tasks."""
    print(f"⚙️ Engineering processing: {task.title}")
    await asyncio.sleep(1.5)
    return TaskResult.success_result(
        data={"features": 5, "bugs_fixed": 12},
        metadata={"department": "engineering"}
    )

async def analytics_handler(task):
    """Handle analytics tasks."""
    print(f"📈 Analytics processing: {task.title}")
    await asyncio.sleep(1)
    return TaskResult.success_result(
        data={"metrics": {"growth": 0.15, "retention": 0.89}},
        metadata={"department": "analytics"}
    )

async def main():
    """Main example demonstrating hierarchical workspaces."""
    print("🏢 Hierarchical Workspace Example")
    print("=" * 45)
    
    # Create department workspaces
    sales_workspace = Workspace("Sales Department")
    engineering_workspace = Workspace("Engineering Department")
    analytics_workspace = Workspace("Analytics Department")
    
    # Build department teams
    print("\n🏬 Building Department Workspaces:")
    print("-" * 35)
    
    async with sales_workspace as sales:
        # Sales team
        sales_team = await sales.team("Direct Sales")
            .with_agent("SalesRep1", ["lead_generation", "sales_data"])
            .with_agent("SalesRep2", ["customer_relations", "crm_access"])
            .build()
        
        # Register handlers
        for agent_id in sales_team.members:
            agent = sales.get_agent(agent_id)
            agent.register_task_handler("sales", sales_handler)
            agent.register_task_handler("lead_generation", sales_handler)
        
        print(f"✅ Sales workspace: {sales.name}")
        print(f"   Capabilities: {sorted(sales.capabilities)}")
    
    async with engineering_workspace as eng:
        # Engineering teams
        backend_team = await eng.team("Backend Team")
            .with_lead("TechLead", ["architecture", "code_review"])
            .with_agent("Developer1", ["python", "api_development"])
            .with_agent("Developer2", ["database", "optimization"])
            .build()
        
        frontend_team = await eng.team("Frontend Team")
            .with_agent("UIDesigner", ["ui_design", "user_experience"])
            .with_agent("FrontendDev", ["javascript", "react"])
            .build()
        
        # Register handlers
        for team in [backend_team, frontend_team]:
            for agent_id in team.members:
                agent = eng.get_agent(agent_id)
                agent.register_task_handler("development", engineering_handler)
                agent.register_task_handler("architecture", engineering_handler)
        
        print(f"✅ Engineering workspace: {eng.name}")
        print(f"   Teams: {len(eng.list_teams())}")
        print(f"   Capabilities: {sorted(eng.capabilities)}")
    
    async with analytics_workspace as analytics:
        # Analytics team
        insights_team = await analytics.team("Data Insights")
            .with_agent("DataScientist", ["ml_predictions", "statistical_analysis"])
            .with_agent("BusinessAnalyst", ["business_intelligence", "reporting"])
            .build()
        
        # Register handlers
        for agent_id in insights_team.members:
            agent = analytics.get_agent(agent_id)
            agent.register_task_handler("analysis", analytics_handler)
            agent.register_task_handler("ml_predictions", analytics_handler)
        
        print(f"✅ Analytics workspace: {analytics.name}")
        print(f"   Capabilities: {sorted(analytics.capabilities)}")
    
    # Create enterprise workspace and connect departments
    print("\n🌟 Creating Enterprise Workspace:")
    print("-" * 32)
    
    enterprise = Workspace("MegaCorp Enterprise")
        .add(sales_workspace)
        .add(engineering_workspace)
        .add(analytics_workspace)
    
    async with enterprise:
        print(f"✅ Enterprise workspace: {enterprise.name}")
        print(f"   Child workspaces: {list(enterprise.children.keys())}")
        print(f"   Total capabilities: {len(enterprise.capabilities)}")
        print(f"   All capabilities: {sorted(enterprise.capabilities)}")
        
        # Create cross-functional team at enterprise level
        strategy_team = await enterprise.team("Strategic Planning")
            .with_agent("StrategicPlanner", ["strategic_planning", "business_strategy"])
            .with_agent("ExecutiveAnalyst", ["executive_reporting", "kpi_analysis"])
            .build()
        
        # Register handlers
        for agent_id in strategy_team.members:
            agent = enterprise.get_agent(agent_id)
            agent.register_task_handler("strategic_planning", analytics_handler)
            agent.register_task_handler("executive_reporting", analytics_handler)
        
        print(f"✅ Cross-functional team: {strategy_team.name}")
        
        # Execute various tasks to demonstrate routing
        print("\n⚡ Executing Cross-Department Tasks:")
        print("-" * 38)
        
        # Task 1: Automatic routing to sales department
        task1 = Task("Generate Q4 Sales Report")
        # Workspace will auto-plan and route to sales department
        plan_id1 = await enterprise.execute(task1)
        completed1 = await enterprise.wait_for_completion(plan_id1, timeout=5)
        print(f"Task 1 routed automatically: {'✅' if completed1 else '❌'}")
        
        # Task 2: Multi-department task requiring coordination
        task2 = Task.create("Product Performance Analysis")
            .requires("sales_data", "user_experience", "statistical_analysis")
            .with_data(product="WebApp", timeframe="Q4")
            .build()
        
        plan_id2 = await enterprise.execute(task2)
        completed2 = await enterprise.wait_for_completion(plan_id2, timeout=8)
        print(f"Cross-department task: {'✅' if completed2 else '❌'}")
        
        # Task 3: Strategic planning (enterprise-level team)
        task3 = Task("2025 Strategic Planning", 
                    task_type="strategic_planning",
                    requires=["strategic_planning"])
        
        result3 = await strategy_team.execute(task3)
        print(f"Strategic task result: {'✅' if result3.success else '❌'}")
        
        # Show comprehensive system status
        print(f"\n📊 Enterprise System Status:")
        print("-" * 28)
        status = enterprise.get_system_status()
        
        print(f"Enterprise: {status['workspace']}")
        print(f"Departments: {len(status['children'])}")
        print(f"Total teams: {status['teams']['total']}")
        print(f"Total agents: {status['agents']['total']}")
        print(f"Unique capabilities: {len(status['capabilities'])}")
        print(f"Tasks completed: {status['tasks']['completed']}")
        
        # Show department-specific stats
        for dept_name, dept_workspace in enterprise.children.items():
            dept_status = dept_workspace.get_system_status()
            print(f"\n  {dept_name}:")
            print(f"    Teams: {dept_status['teams']['total']}")
            print(f"    Agents: {dept_status['agents']['total']}")
            print(f"    Capabilities: {len(dept_status['capabilities'])}")
        
        print("\n🎉 Hierarchical workspace example completed!")

if __name__ == "__main__":
    asyncio.run(main())