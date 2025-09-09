"""
Example demonstrating the agentic framework with team-based orchestration.

This example shows how to:
1. Create agents with different capabilities
2. Form teams with team leads
3. Compose teams within other teams
4. Execute complex tasks with automatic decomposition
5. Monitor execution progress
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Dict, Any

# Add parent directory to path for direct execution
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agentic_framework import (
    AgenticFramework, 
    Task, 
    TaskResult, 
    TaskPriority, 
    TaskBuilder,
    Agent,
    RedisMessageBus
)


# Example task handlers for different agent types
async def data_collection_handler(task: Task) -> TaskResult:
    """Handle data collection tasks."""
    print(f"🔍 Collecting data for task: {task.title}")
    
    # Simulate data collection work
    await asyncio.sleep(2)
    
    # Return collected data
    collected_data = {
        "records": 1000,
        "sources": ["database", "api", "files"],
        "timestamp": "2024-01-01T12:00:00Z"
    }
    
    return TaskResult.success_result(
        data=collected_data,
        metadata={"collection_time": 2, "data_quality": "high"}
    )


async def analysis_handler(task: Task) -> TaskResult:
    """Handle analysis tasks."""
    print(f"📊 Analyzing data for task: {task.title}")
    
    # Simulate analysis work
    await asyncio.sleep(3)
    
    input_data = task.input_data.get("collected_data", {})
    records = input_data.get("records", 0)
    
    analysis_results = {
        "insights": [
            "Sales increased by 15% this quarter",
            "Customer satisfaction improved",
            "Processing time reduced by 20%"
        ],
        "metrics": {
            "accuracy": 0.95,
            "confidence": 0.88,
            "processed_records": records
        }
    }
    
    return TaskResult.success_result(
        data=analysis_results,
        metadata={"analysis_time": 3, "model_version": "v2.1"}
    )


async def reporting_handler(task: Task) -> TaskResult:
    """Handle report generation tasks."""
    print(f"📄 Generating report for task: {task.title}")
    
    # Simulate report generation
    await asyncio.sleep(1.5)
    
    report_content = {
        "title": f"Analysis Report: {task.title}",
        "executive_summary": "This report presents key findings from the recent analysis.",
        "sections": [
            "Data Overview",
            "Key Insights", 
            "Recommendations",
            "Next Steps"
        ],
        "attachments": ["charts.pdf", "raw_data.csv"]
    }
    
    return TaskResult.success_result(
        data=report_content,
        metadata={"report_length": 25, "format": "pdf"}
    )


async def computation_handler(task: Task) -> TaskResult:
    """Handle computational tasks."""
    print(f"🧮 Computing for task: {task.title}")
    
    # Simulate computational work
    await asyncio.sleep(2.5)
    
    computation_results = {
        "calculations": {
            "total_revenue": 1250000,
            "growth_rate": 0.15,
            "efficiency_score": 0.87
        },
        "models_executed": ["regression", "classification", "clustering"],
        "processing_stats": {
            "cpu_time": 125.5,
            "memory_used": "2.3GB"
        }
    }
    
    return TaskResult.success_result(
        data=computation_results,
        metadata={"complexity": "high", "optimization_level": "standard"}
    )


async def coordination_handler(task: Task) -> TaskResult:
    """Handle coordination tasks for team leads."""
    print(f"🎯 Coordinating task: {task.title}")
    
    # Simulate coordination work
    await asyncio.sleep(1)
    
    coordination_result = {
        "plan_created": True,
        "subtasks_identified": len(task.subtask_ids),
        "resource_allocation": "optimal",
        "timeline": "on_track"
    }
    
    return TaskResult.success_result(
        data=coordination_result,
        metadata={"coordination_time": 1, "team_size": 3}
    )


async def main():
    """Main example execution."""
    print("🚀 Starting Agentic Framework Example")
    print("=" * 50)
    
    # Create framework instance with Redis message bus
    try:
        framework = AgenticFramework(message_bus=RedisMessageBus("redis://localhost:6379"))
    except Exception as e:
        print(f"⚠️  Could not connect to Redis. Using in-memory message bus for demo.")
        # In production, you'd implement an in-memory message bus
        # For this demo, we'll show the structure without actual execution
        await demo_structure()
        return
    
    async with framework:
        print("✅ Framework started successfully")
        
        # Create specialized agents
        print("\n📋 Creating Agents:")
        print("-" * 20)
        
        # Data team agents
        data_collector = framework.create_agent(
            name="DataCollector-001",
            agent_type="data_collector",
            capabilities=["data_access", "collection", "extraction"],
            max_concurrent_tasks=2
        )
        data_collector.register_task_handler("data_collection", data_collection_handler)
        data_collector.register_task_handler("data_preparation", data_collection_handler)
        
        # Analysis team agents
        analyst = framework.create_agent(
            name="Analyst-001",
            agent_type="analyst",
            capabilities=["analysis", "statistics", "machine_learning"],
            max_concurrent_tasks=1
        )
        analyst.register_task_handler("analysis", analysis_handler)
        
        compute_agent = framework.create_agent(
            name="ComputeEngine-001", 
            agent_type="compute",
            capabilities=["computation", "parallel_processing", "optimization"],
            max_concurrent_tasks=3
        )
        compute_agent.register_task_handler("computation", computation_handler)
        
        # Reporting team agents
        reporter = framework.create_agent(
            name="Reporter-001",
            agent_type="reporter", 
            capabilities=["writing", "visualization", "reporting"],
            max_concurrent_tasks=2
        )
        reporter.register_task_handler("reporting", reporting_handler)
        reporter.register_task_handler("report_generation", reporting_handler)
        
        # Create team leads
        print("\n👨‍💼 Creating Team Leads:")
        print("-" * 25)
        
        data_team_lead = framework.create_team_lead(
            name="DataTeamLead-001",
            capabilities=["coordination", "planning", "data_domain"],
            max_concurrent_tasks=5
        )
        data_team_lead.register_task_handler("coordination", coordination_handler)
        data_team_lead.register_task_handler("planning", coordination_handler)
        
        analysis_team_lead = framework.create_team_lead(
            name="AnalysisTeamLead-001", 
            capabilities=["coordination", "planning", "analysis_domain"],
            max_concurrent_tasks=5
        )
        analysis_team_lead.register_task_handler("coordination", coordination_handler)
        analysis_team_lead.register_task_handler("planning", coordination_handler)
        
        # Create teams
        print("\n🏢 Creating Teams:")
        print("-" * 18)
        
        # Data team
        data_team = framework.create_team(
            name="Data Collection Team",
            description="Responsible for data collection and preparation",
            max_concurrent_tasks=5
        )
        framework.add_agent_to_team(data_team_lead.id, data_team.id, "lead")
        framework.add_agent_to_team(data_collector.id, data_team.id, "member")
        
        # Analysis team  
        analysis_team = framework.create_team(
            name="Analysis Team",
            description="Handles data analysis and computational tasks",
            max_concurrent_tasks=8
        )
        framework.add_agent_to_team(analysis_team_lead.id, analysis_team.id, "lead")
        framework.add_agent_to_team(analyst.id, analysis_team.id, "member")
        framework.add_agent_to_team(compute_agent.id, analysis_team.id, "member")
        
        # Reporting team (no dedicated lead, using analysis team lead)
        reporting_team = framework.create_team(
            name="Reporting Team", 
            description="Creates reports and visualizations",
            max_concurrent_tasks=3
        )
        framework.add_agent_to_team(analysis_team_lead.id, reporting_team.id, "lead") 
        framework.add_agent_to_team(reporter.id, reporting_team.id, "member")
        
        # Create a super team that combines all teams
        print("\n🌟 Creating Super Team (Team Composition):")
        print("-" * 45)
        
        super_team = framework.create_team(
            name="Enterprise Analytics Team",
            description="Complete analytics solution with data, analysis, and reporting capabilities",
            max_concurrent_tasks=15
        )
        
        # Add teams as members of the super team
        framework.add_team_to_team(data_team.id, super_team.id, "data_specialist")
        framework.add_team_to_team(analysis_team.id, super_team.id, "analysis_specialist")
        framework.add_team_to_team(reporting_team.id, super_team.id, "reporting_specialist")
        
        # Show system status
        print("\n📊 System Status:")
        print("-" * 18)
        status = framework.get_system_status()
        print(f"Agents: {status['agents']['total']} total, {status['agents']['active']} active")
        print(f"Teams: {status['teams']['total']} total, {status['teams']['active']} active")
        
        # Execute a complex analysis task
        print("\n🎯 Executing Complex Analysis Task:")
        print("-" * 38)
        
        complex_task = framework.create_task(
            title="Q4 2024 Business Intelligence Analysis",
            task_type="complex_analysis",
            description="Complete analysis of Q4 business performance with recommendations",
            input_data={
                "quarter": "Q4-2024",
                "data_sources": ["sales_db", "customer_db", "financial_db"],
                "analysis_types": ["revenue", "customer_satisfaction", "efficiency"],
                "output_format": "executive_report"
            },
            required_capabilities=["data_access", "analysis", "reporting"],
            priority=TaskPriority.HIGH
        )
        
        print(f"Task created: {complex_task.title}")
        print(f"Task ID: {complex_task.id}")
        print(f"Required capabilities: {complex_task.required_capabilities}")
        
        # Execute using super team
        print(f"\n⚡ Executing task with super team...")
        plan_id = await framework.execute_task(complex_task, super_team.id)
        print(f"Execution plan created: {plan_id}")
        
        # Wait for completion with timeout
        print("\n⏳ Waiting for task completion...")
        completed = await framework.wait_for_completion(plan_id, timeout=30)
        
        if completed:
            print("✅ Task completed successfully!")
            
            # Show final system status
            print("\n📈 Final System Status:")
            print("-" * 24)
            final_status = framework.get_system_status()
            print(f"Tasks completed: {final_status['tasks']['completed']}")
            print(f"Tasks failed: {final_status['tasks']['failed']}")
            print(f"Average task duration: {final_status['average_task_duration']:.2f}s")
            print(f"System load: {final_status['system_load']:.1%}")
        else:
            print("⚠️ Task did not complete within timeout")
        
        # Execute a simpler task to show direct assignment
        print("\n🔧 Executing Simple Task (Direct Assignment):")
        print("-" * 50)
        
        simple_task = framework.create_task(
            title="Generate Monthly Sales Report",
            task_type="reporting",
            description="Create a standard monthly sales report",
            input_data={
                "month": "December 2024",
                "template": "monthly_sales",
                "format": "pdf"
            },
            required_capabilities=["reporting", "visualization"],
            priority=TaskPriority.NORMAL
        )
        
        print(f"Simple task: {simple_task.title}")
        plan_id_2 = await framework.execute_task(simple_task, reporting_team.id)
        await framework.wait_for_completion(plan_id_2, timeout=15)
        
        print("\n🎉 Example execution completed!")
        print("=" * 50)


async def demo_structure():
    """Demo the structure without actual execution (for when Redis is not available)."""
    print("📚 Demo: Framework Structure Overview")
    print("=" * 40)
    
    print("\n🏗️  Architecture Components:")
    print("1. AgenticFramework - Main orchestrator")
    print("2. MessageBus - Communication layer (Redis/SQS)")
    print("3. Agents - Individual workers with capabilities")
    print("4. Teams - Groups of agents with leads")
    print("5. Tasks - Work units with requirements")
    print("6. Orchestration - Planning, dispatching, monitoring")
    
    print("\n🔄 Execution Flow:")
    print("1. Create agents with specific capabilities")
    print("2. Form teams and assign team leads")  
    print("3. Compose teams within super teams")
    print("4. Submit complex tasks to framework")
    print("5. Framework decomposes tasks into subtasks")
    print("6. Team leads create execution plans")
    print("7. Tasks distributed to capable agents")
    print("8. Results aggregated and reviewed")
    print("9. Progress monitored and reported")
    
    print("\n🌟 Key Features Demonstrated:")
    print("✅ Multi-agent coordination")
    print("✅ Hierarchical team structure") 
    print("✅ Team composition (teams as members)")
    print("✅ Automatic task decomposition")
    print("✅ Capability-based assignment")
    print("✅ Parallel and distributed execution")
    print("✅ Real-time monitoring")
    print("✅ Message-driven architecture")
    
    print(f"\n📋 Example Task Types:")
    print("• Data Collection → Agent with data_access capability")
    print("• Analysis → Agent with analysis capability")
    print("• Reporting → Agent with reporting capability")
    print("• Coordination → TeamLead with planning capability")
    
    print(f"\n🎯 To run with full execution:")
    print("1. Start Redis: docker run -p 6379:6379 redis")
    print("2. Run: python -m agentic_framework.examples.example_team")


if __name__ == "__main__":
    asyncio.run(main())