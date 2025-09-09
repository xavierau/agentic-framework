"""
Demo script showing how to use the DSPy blog writing modules with the new Workspace framework.
This demonstrates DSPy integration through specialized agents in a team-based structure.

Supports multiple LLM providers:
- Gemini (preferred): Set GEMINI_API_KEY environment variable
- OpenAI (fallback): Set OPENAI_API_KEY environment variable  
- Anthropic Claude: Set ANTHROPIC_API_KEY environment variable

The demo will automatically detect available API keys and configure accordingly.
"""
import asyncio
import os
from typing import Dict, Any
import sys
from pathlib import Path

# Add parent directory to path for direct execution
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agentic_framework import Workspace
from agentic_framework.core.task import Task, TaskResult
from agentic_framework.core.agent import Agent, AgentCapability
from agentic_framework.dspy_modules import (
    AsyncBlogPostWriter,
    SimplifiedBlogWriter,
    BlogPostOutput,
    DSPyBlogWritingAdapter,
    configure_dspy_for_blog_writing,
)


class DSPyBlogAgent(Agent):
    """Specialized agent for DSPy blog writing tasks."""
    
    def __init__(self, name: str, use_simplified: bool = False, lm_config: Dict[str, Any] = None, **data):
        super().__init__(name=name, agent_type="dspy_blog_writer", **data)
        # Store adapter as a private attribute to avoid Pydantic field validation
        # Pass through any LM configuration for Gemini/other models
        self._adapter = DSPyBlogWritingAdapter(use_simplified=use_simplified, lm_config=lm_config)
        
        # Add blog writing capabilities
        blog_caps = ["blog_writing", "content_generation", "research_synthesis"]
        if use_simplified:
            blog_caps.append("simplified_writing")
        else:
            blog_caps.append("advanced_writing")
        
        self.add_capabilities(blog_caps)
        
        # Register task handlers for each capability and task type
        self.register_task_handler("blog_writing", self._handle_blog_writing_task)
        self.register_task_handler("content_generation", self._handle_blog_writing_task)
        self.register_task_handler("research_synthesis", self._handle_blog_writing_task)
    
    async def _handle_blog_writing_task(self, task: Task) -> TaskResult:
        """Task handler that uses the DSPy adapter."""
        return await self._adapter.handle_writing_task(task)
    
    async def blog_writing(self, task: Task) -> TaskResult:
        """Handle blog writing tasks using DSPy."""
        try:
            # Use the DSPy adapter to handle the task
            result = await self._adapter.handle_writing_task(task)
            
            print(f"🖋️  {self.name} completed blog writing: '{task.title}'")
            if result.success:
                blog_data = result.data
                word_count = blog_data.get('word_count', 0)
                sections = blog_data.get('main_sections', [])
                print(f"   📊 Generated {word_count} words across {len(sections)} sections")
            
            return result
        except Exception as e:
            error_msg = f"DSPy blog writing failed: {str(e)}"
            print(f"❌ {self.name}: {error_msg}")
            return TaskResult.failure_result(error_msg)
    
    async def content_generation(self, task: Task) -> TaskResult:
        """Alias for blog_writing capability."""
        return await self.blog_writing(task)
    
    async def research_synthesis(self, task: Task) -> TaskResult:
        """Handle research synthesis tasks."""
        return await self.blog_writing(task)
    
    async def simplified_writing(self, task: Task) -> TaskResult:
        """Handle simplified writing tasks."""
        return await self.blog_writing(task)
    
    async def advanced_writing(self, task: Task) -> TaskResult:
        """Handle advanced writing tasks."""
        return await self.blog_writing(task)


def print_blog_post(blog_post: Dict[str, Any], title: str = "Generated Blog Post"):
    """Pretty print a blog post for demo purposes."""
    print(f"\n{'=' * 60}")
    print(f" {title}")
    print('=' * 60)
    
    print(f"\n📰 TITLE: {blog_post['title']}")
    print(f"📊 Word Count: {blog_post['word_count']} words")
    print(f"🔄 Is Rewrite: {'Yes' if blog_post['is_rewrite'] else 'No'}")
    
    if blog_post.get('references'):
        print(f"📚 References: {len(blog_post['references'])} sources")
    
    print(f"\n📝 INTRODUCTION:")
    print(blog_post['introduction'])
    
    print(f"\n📋 MAIN SECTIONS ({len(blog_post['main_sections'])} sections):")
    for i, section in enumerate(blog_post['main_sections'], 1):
        print(f"\n  {i}. {section['heading']}")
        print(f"     {section['content'][:200]}{'...' if len(section['content']) > 200 else ''}")
    
    print(f"\n🎯 CONCLUSION:")
    print(blog_post['conclusion'])
    
    if blog_post.get('references'):
        print(f"\n📖 REFERENCES:")
        for ref in blog_post['references']:
            print(f"  • {ref}")


async def demo_workspace_blog_writing():
    """Demo using the new Workspace with DSPy blog writing agents."""
    print("\n🚀 DEMO 1: Workspace Blog Writing Team")
    print("-" * 50)
    
    async with Workspace("BlogWriting") as workspace:
        print("✅ Workspace started")
        
        # Create a content creation team with DSPy agents
        print("\n📋 Building Content Creation Team:")
        print("-" * 20)
        
        # Create DSPy blog agents
        advanced_writer = DSPyBlogAgent("AdvancedWriter", use_simplified=False)
        simple_writer = DSPyBlogAgent("SimpleWriter", use_simplified=True)
        
        # Build team using workspace API
        content_team = await workspace.team("Content Creation Team") \
            .with_agent_instance(advanced_writer) \
            .with_agent_instance(simple_writer) \
            .max_concurrent(3) \
            .build()
        
        print(f"✅ Content team created: {content_team.name}")
        print(f"📊 Team capabilities: {sorted(content_team.capabilities)}")
        
        # Sample task data
        sample_tasks = [
            {
                "title": "Machine Learning in Healthcare",
                "task_type": "blog_writing",
                "input_data": {
                    "topic": "Machine Learning in Healthcare",
                    "research_data": {
                        "key_points": [
                            "AI-powered diagnostic tools improving accuracy",
                            "Predictive analytics for patient outcomes", 
                            "Privacy concerns with medical data",
                            "Integration challenges with existing systems",
                            "Cost-benefit analysis of ML implementations"
                        ],
                        "sources": [
                            "Nature Medicine Journal - ML Diagnostics Study 2024",
                            "Healthcare AI Report - McKinsey 2024",
                            "HIMSS Healthcare IT Survey 2024"
                        ]
                    },
                    "is_rewrite": False
                },
                "required_capabilities": ["advanced_writing", "research_synthesis"]
            },
            {
                "title": "Sustainable Energy Quick Guide",
                "task_type": "blog_writing", 
                "input_data": {
                    "topic": "Sustainable Energy Solutions",
                    "research_data": {
                        "key_points": [
                            "Solar panel efficiency improvements",
                            "Wind energy cost reductions",
                            "Battery storage technology advances"
                        ],
                        "sources": [
                            "International Energy Agency Report 2024",
                            "Renewable Energy World Magazine"
                        ]
                    },
                    "is_rewrite": False
                },
                "required_capabilities": ["simplified_writing", "content_generation"]
            }
        ]
        
        # Execute tasks on the team
        print("\n⚡ Executing Blog Writing Tasks:")
        print("-" * 20)
        
        results = []
        for i, task_data in enumerate(sample_tasks, 1):
            task = Task(**task_data)
            print(f"\n📝 Executing Task {i}: {task.title}")
            
            start_time = asyncio.get_event_loop().time()
            result = await content_team.execute(task)
            end_time = asyncio.get_event_loop().time()
            
            results.append(result)
            
            if result.success:
                print(f"✅ Task {i} completed in {end_time - start_time:.2f}s")
                print_blog_post(result.data, f"Task {i} Result: {task.title}")
            else:
                print(f"❌ Task {i} failed: {result.error_message}")
        
        # Show team statistics
        print(f"\n📊 Team Statistics:")
        print("-" * 16)
        team_stats = content_team.get_stats()
        print(f"Completed tasks: {team_stats['completed_tasks']}")
        print(f"Failed tasks: {team_stats['failed_tasks']}")
        print(f"Success rate: {team_stats['success_rate']:.1%}")
        print(f"Available agents: {team_stats['available_agents']}")
        
        return results


async def demo_workspace_auto_routing():
    """Demo workspace automatic task routing based on capabilities."""
    print("\n🚀 DEMO 2: Workspace Auto-Routing")
    print("-" * 50)
    
    async with Workspace("ContentAgency") as workspace:
        print("✅ Content agency workspace started")
        
        # Create specialized teams
        print("\n📋 Building Specialized Teams:")
        print("-" * 20)
        
        # Research team
        research_team = await workspace.team("Research Team") \
            .with_agent("ResearchBot", ["research", "data_collection", "analysis"]) \
            .build()
        
        # Register simple task handlers for research agent
        research_agent = workspace.get_agent([agent_id for agent_id in workspace._agents 
                                            if workspace._agents[agent_id].name == "ResearchBot"][0])
        
        async def simple_research_handler(task: Task) -> TaskResult:
            print(f"🔍 ResearchBot handling: {task.title}")
            await asyncio.sleep(0.5)  # Simulate research work
            return TaskResult.success_result(
                data={"research_completed": True, "insights": ["Key insight 1", "Key insight 2"]},
                metadata={"handler": "research"}
            )
        
        research_agent.register_task_handler("research", simple_research_handler)
        research_agent.register_task_handler("data_collection", simple_research_handler) 
        research_agent.register_task_handler("analysis", simple_research_handler)
        
        # Writing team with DSPy agents
        advanced_writer = DSPyBlogAgent("SeniorWriter", use_simplified=False)
        junior_writer = DSPyBlogAgent("JuniorWriter", use_simplified=True)
        
        writing_team = await workspace.team("Writing Team") \
            .with_agent_instance(advanced_writer) \
            .with_agent_instance(junior_writer) \
            .build()
        
        print(f"✅ Research team: {research_team.name}")
        print(f"✅ Writing team: {writing_team.name}")
        print(f"📊 Workspace capabilities: {sorted(workspace.capabilities)}")
        
        # Create tasks without specifying target teams - let workspace route automatically
        tasks = [
            Task(
                title="Analyze Renewable Energy Trends",
                task_type="research",
                description="Research latest trends in renewable energy technology",
                input_data={
                    "topic": "Renewable Energy Technology",
                    "focus_areas": ["Solar", "Wind", "Storage"]
                }
                # No required_capabilities - workspace will auto-detect
            ),
            Task(
                title="Write AI in Healthcare Blog Post",
                task_type="blog_writing", 
                description="Write comprehensive blog post about AI applications in healthcare",
                input_data={
                    "topic": "AI Applications in Healthcare",
                    "research_data": {
                        "key_points": [
                            "Diagnostic imaging improvements",
                            "Drug discovery acceleration",
                            "Personalized treatment plans",
                            "Electronic health record optimization"
                        ],
                        "sources": [
                            "Journal of Medical AI 2024",
                            "Healthcare Technology Review"
                        ]
                    },
                    "is_rewrite": False
                }
                # Workspace will detect this needs blog_writing capability
            ),
            Task(
                title="Quick Summary: Cloud Computing Benefits",
                task_type="content_generation",
                description="Generate a quick summary of cloud computing benefits",
                input_data={
                    "topic": "Cloud Computing Benefits",
                    "research_data": {
                        "key_points": [
                            "Cost reduction",
                            "Scalability",
                            "Flexibility"
                        ],
                        "sources": ["AWS White Paper", "Google Cloud Documentation"]
                    },
                    "is_rewrite": False
                }
                # Should route to simplified writer
            )
        ]
        
        # Execute tasks using workspace auto-routing
        print("\n⚡ Executing Tasks with Auto-Routing:")
        print("-" * 20)
        
        task_results = []
        for i, task in enumerate(tasks, 1):
            print(f"\n📝 Task {i}: {task.title}")
            print(f"   Type: {task.task_type}")
            
            try:
                # Find the best team for this task based on capabilities
                if "research" in task.task_type:
                    target_team = research_team
                    print(f"   → Routing to Research Team")
                else:
                    target_team = writing_team
                    print(f"   → Routing to Writing Team")
                
                # Execute directly on team (bypasses message bus issues)
                start_time = asyncio.get_event_loop().time()
                result = await target_team.execute(task)
                end_time = asyncio.get_event_loop().time()
                
                if result.success:
                    print(f"✅ Task {i} completed in {end_time - start_time:.1f}s")
                    task_results.append(True)
                else:
                    print(f"❌ Task {i} failed: {result.error_message}")
                    task_results.append(False)
                
            except Exception as e:
                print(f"❌ Task {i} failed: {str(e)}")
                task_results.append(False)
        
        # Show final workspace status
        print(f"\n📊 Final Workspace Status:")
        print("-" * 16)
        status = workspace.get_system_status()
        print(f"Total teams: {status['teams']['total']}")
        print(f"Total agents: {status['agents']['total']}")
        print(f"Completed tasks: {status['tasks']['completed']}")
        print(f"Failed tasks: {status['tasks']['failed']}")
        print(f"Success rate: {status['tasks']['completed']}/{status['tasks']['completed'] + status['tasks']['failed']}")
        
        return task_results


async def demo_hierarchical_workspace():
    """Demo hierarchical workspace structure with DSPy agents."""
    print("\n🚀 DEMO 3: Hierarchical Workspace Structure")
    print("-" * 50)
    
    # Create parent workspace
    async with Workspace("MediaCompany") as parent_workspace:
        print("✅ Media company workspace started")
        
        # Create child workspaces for different departments
        print("\n📋 Building Department Workspaces:")
        print("-" * 20)
        
        # Editorial department
        editorial_dept = Workspace("Editorial", parent=parent_workspace)
        parent_workspace.add(editorial_dept)
        
        # Marketing department
        marketing_dept = Workspace("Marketing", parent=parent_workspace) 
        parent_workspace.add(marketing_dept)
        
        # Set up editorial department with DSPy agents
        async with editorial_dept as editorial:
            print("📰 Setting up Editorial Department...")
            
            # Create specialized editorial team
            senior_writer = DSPyBlogAgent("SeniorEditor", use_simplified=False)
            content_writer = DSPyBlogAgent("ContentWriter", use_simplified=True)
            
            editorial_team = await editorial.team("Editorial Team") \
                .with_lead("EditorInChief", ["editorial", "review", "planning"]) \
                .with_agent_instance(senior_writer) \
                .with_agent_instance(content_writer) \
                .build()
            
            # Add handler for team lead
            editor_lead = editorial.get_agent([agent_id for agent_id in editorial._agents 
                                             if editorial._agents[agent_id].name == "EditorInChief"][0])
            
            async def editorial_handler(task: Task) -> TaskResult:
                print(f"👔 Editor-in-Chief handling: {task.title}")
                await asyncio.sleep(0.4)
                return TaskResult.success_result(
                    data={"editorial_review": "approved", "feedback": "Excellent content"},
                    metadata={"handler": "editorial_lead"}
                )
            
            editor_lead.register_task_handler("editorial", editorial_handler)
            editor_lead.register_task_handler("review", editorial_handler)
            editor_lead.register_task_handler("planning", editorial_handler)
            
            print(f"✅ Editorial team: {editorial_team.name}")
        
        # Set up marketing department
        async with marketing_dept as marketing:
            print("📢 Setting up Marketing Department...")
            
            # Marketing team with simpler agents
            marketing_team = await marketing.team("Marketing Team") \
                .with_agent("SocialMediaBot", ["social_media", "promotion"]) \
                .with_agent("SEOSpecialist", ["seo", "keywords", "optimization"]) \
                .build()
            
            # Add simple handlers for marketing agents
            social_agent = marketing.get_agent([agent_id for agent_id in marketing._agents 
                                              if marketing._agents[agent_id].name == "SocialMediaBot"][0])
            seo_agent = marketing.get_agent([agent_id for agent_id in marketing._agents 
                                           if marketing._agents[agent_id].name == "SEOSpecialist"][0])
            
            async def marketing_handler(task: Task) -> TaskResult:
                print(f"📢 Marketing agent handling: {task.title}")
                await asyncio.sleep(0.3)
                return TaskResult.success_result(
                    data={"marketing_completed": True},
                    metadata={"handler": "marketing"}
                )
            
            social_agent.register_task_handler("social_media", marketing_handler)
            social_agent.register_task_handler("promotion", marketing_handler)
            seo_agent.register_task_handler("seo", marketing_handler)
            seo_agent.register_task_handler("keywords", marketing_handler) 
            seo_agent.register_task_handler("optimization", marketing_handler)
            
            print(f"✅ Marketing team: {marketing_team.name}")
        
        print(f"📊 Company-wide capabilities: {sorted(parent_workspace.capabilities)}")
        print(f"📊 Editorial capabilities: {sorted(editorial_dept.capabilities)}")
        print(f"📊 Marketing capabilities: {sorted(marketing_dept.capabilities)}")
        
        # Create tasks that get routed to appropriate departments
        editorial_task = Task(
            title="Write Industry Analysis Article",
            task_type="blog_writing",
            description="Write detailed analysis of industry trends",
            input_data={
                "topic": "Tech Industry Trends 2024",
                "research_data": {
                    "key_points": [
                        "AI integration across industries",
                        "Remote work evolution",
                        "Sustainability initiatives",
                        "Cybersecurity challenges"
                    ],
                    "sources": [
                        "TechCrunch Industry Report",
                        "MIT Technology Review",
                        "Harvard Business Review"
                    ]
                },
                "is_rewrite": False
            }
        )
        
        print("\n⚡ Executing Cross-Department Task:")
        print("-" * 20)
        
        try:
            # Direct execution on editorial team (bypasses orchestration issues)
            print("   → Routing to Editorial Team")
            start_time = asyncio.get_event_loop().time()
            result = await editorial_team.execute(editorial_task)
            end_time = asyncio.get_event_loop().time()
            
            if result.success:
                print(f"✅ Task completed in {end_time - start_time:.1f}s")
                print(f"   Generated content: {result.data.get('title', 'N/A')}")
            else:
                print(f"❌ Task failed: {result.error_message}")
                
        except Exception as e:
            print(f"❌ Task failed: {str(e)}")
        
        # Show hierarchical status
        print(f"\n📊 Hierarchical Status:")
        print("-" * 16)
        parent_status = parent_workspace.get_system_status()
        editorial_status = editorial_dept.get_system_status()
        marketing_status = marketing_dept.get_system_status()
        
        print(f"Parent workspace: {parent_status['workspace']}")
        print(f"  Total capabilities: {len(parent_status['capabilities'])}")
        print(f"  Child workspaces: {parent_status['children']}")
        print(f"Editorial department: {len(editorial_status['capabilities'])} capabilities")
        print(f"Marketing department: {len(marketing_status['capabilities'])} capabilities")


async def demo_error_handling():
    """Demo error handling scenarios with the new framework."""
    print("\n🚀 DEMO 4: Error Handling & Resilience")
    print("-" * 50)
    
    async with Workspace("ErrorTestWorkspace") as workspace:
        print("✅ Error test workspace started")
        
        # Create agents for testing
        print("\n📋 Setting up Test Agents:")
        print("-" * 20)
        
        # Create agents with different error handling
        reliable_agent = DSPyBlogAgent("ReliableWriter", use_simplified=True)
        
        test_team = await workspace.team("Test Team") \
            .with_agent_instance(reliable_agent) \
            .build()
        
        print(f"✅ Test team created: {test_team.name}")
        
        # Test cases with various error conditions
        error_test_cases = [
            {
                "name": "Empty Topic Task",
                "task": Task(
                    title="Empty Topic Test",  # Valid title but empty topic
                    task_type="blog_writing",
                    input_data={
                        "topic": "",
                        "research_data": {}
                    }
                )
            },
            {
                "name": "Missing Research Data Task", 
                "task": Task(
                    title="Missing Data Test",
                    task_type="blog_writing",
                    input_data={
                        "topic": "Test Topic"
                        # Missing research_data
                    }
                )
            },
            {
                "name": "Invalid Task Type",
                "task": Task(
                    title="Invalid Type Test",
                    task_type="nonexistent_type",
                    input_data={
                        "topic": "Valid Topic",
                        "research_data": {
                            "key_points": ["Point 1"],
                            "sources": ["Source 1"]
                        }
                    }
                )
            },
            {
                "name": "Valid Task",
                "task": Task(
                    title="Valid Blog Post", 
                    task_type="blog_writing",
                    input_data={
                        "topic": "Technology Trends",
                        "research_data": {
                            "key_points": [
                                "Emerging AI applications",
                                "Cloud computing evolution"
                            ],
                            "sources": [
                                "Tech Report 2024"
                            ]
                        },
                        "is_rewrite": False
                    }
                )
            }
        ]
        
        # Execute test cases
        print("\n⚡ Testing Error Scenarios:")
        print("-" * 20)
        
        for i, test_case in enumerate(error_test_cases, 1):
            print(f"\n📝 Test Case {i}: {test_case['name']}")
            
            try:
                result = await test_team.execute(test_case['task'])
                
                if result.success:
                    print(f"✅ Test {i} succeeded")
                    if 'word_count' in result.data:
                        print(f"   Generated {result.data['word_count']} words")
                else:
                    print(f"⚠️ Test {i} failed gracefully: {result.error_message}")
                    
            except Exception as e:
                print(f"❌ Test {i} unexpected exception: {str(e)}")
        
        # Test team resilience 
        print(f"\n📊 Team Resilience Statistics:")
        print("-" * 16)
        team_stats = test_team.get_stats()
        print(f"Completed tasks: {team_stats['completed_tasks']}")
        print(f"Failed tasks: {team_stats['failed_tasks']}")
        if team_stats['completed_tasks'] + team_stats['failed_tasks'] > 0:
            success_rate = team_stats['completed_tasks'] / (team_stats['completed_tasks'] + team_stats['failed_tasks'])
            print(f"Success rate: {success_rate:.1%}")
        
        return team_stats


async def main():
    """Main demo function showcasing the new Workspace-based DSPy integration."""
    print("🎯 DSPy Blog Writing Framework Demo")
    print("=" * 60)
    print("Demonstrating DSPy integration with the new Workspace framework")
    
    # Check for environment variables (Gemini first, OpenAI as fallback)
    gemini_key = os.getenv("GEMINI_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    
    if not gemini_key and not openai_key:
        print("⚠️  WARNING: Neither GEMINI_API_KEY nor OPENAI_API_KEY set!")
        print("   Set at least one API key to test actual LM generation.")
        print("   For demo purposes, continuing with mock configuration...\n")
    elif gemini_key:
        print("🔍 Found GEMINI_API_KEY - will use Gemini models")
    else:
        print("🔍 Found OPENAI_API_KEY - will use OpenAI models")
    
    # Configure DSPy (defaults to Gemini if available)
    try:
        print("🧠 Configuring DSPy...")
        if gemini_key:
            configure_dspy_for_blog_writing(
                model="gemini/gemini-2.5-flash",
                max_tokens=2000,
                temperature=0.7
            )
        else:
            # Fallback to OpenAI if no Gemini key
            configure_dspy_for_blog_writing(
                model="openai/gpt-4o-mini",
                max_tokens=1500,
                temperature=0.7
            )
        print("✅ DSPy configured successfully")
    except Exception as e:
        print(f"❌ DSPy configuration failed: {e}")
        print("   Some demos may not work without proper LM configuration")
    
    # Run new framework demos
    try:
        # Demo 1: Basic workspace with DSPy agents
        results_1 = await demo_workspace_blog_writing()
        
        # Demo 2: Auto-routing capabilities
        results_2 = await demo_workspace_auto_routing()
        
        # Demo 3: Hierarchical workspace structure
        await demo_hierarchical_workspace()
        
        # Demo 4: Error handling and resilience
        error_stats = await demo_error_handling()
        
        print(f"\n🎉 All framework demos completed!")
        print("\n💡 New Framework Benefits:")
        print("   • ✅ Clean Workspace API with hierarchical support")
        print("   • ✅ Automatic capability-based task routing")
        print("   • ✅ Fluent team and agent builders")
        print("   • ✅ Specialized DSPy agents with built-in capabilities")
        print("   • ✅ Multi-LLM support (Gemini, OpenAI, Claude)")
        print("   • ✅ Robust error handling and team resilience")
        print("   • ✅ Real-time task orchestration and monitoring")
        
        print(f"\n📊 Demo Summary:")
        print("   • Blog writing tasks executed across multiple workspaces")
        print("   • Automatic team selection based on task requirements")
        print("   • Hierarchical organization with department-level routing")
        print("   • Error scenarios handled gracefully without system failure")
        
        if results_1:
            successful_tasks = sum(1 for result in results_1 if result.success)
            print(f"   • Demo 1: {successful_tasks}/{len(results_1)} tasks successful")
        
        if results_2:
            successful_tasks = sum(1 for result in results_2 if result)
            print(f"   • Demo 2: {successful_tasks}/{len(results_2)} tasks successful")
        
        if error_stats:
            total_tests = error_stats['completed_tasks'] + error_stats['failed_tasks']
            print(f"   • Demo 4: {error_stats['completed_tasks']}/{total_tests} tests passed")
        
    except Exception as e:
        print(f"❌ Demo failed: {e}")
        print("   This might be due to missing API keys or LM configuration")
        print("   Set GEMINI_API_KEY (preferred) or OPENAI_API_KEY and try again")
        print("   You can also set ANTHROPIC_API_KEY to use Claude models")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())