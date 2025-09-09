import asyncio
import json
import sys
from pathlib import Path
from typing import Dict, Any

# Add parent directory to path for direct execution
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agentic_framework import (
    Workspace,
    Agent,
    Task,
    TaskResult,
    TaskPriority,
    RedisMessageBus,
    InMemoryMessageBus
)
from agentic_framework.dspy_modules import (
    dspy_writing_handler,
    dspy_writing_handler_simplified,
    configure_dspy_for_blog_writing
)


# Enhanced Agent classes with capabilities as methods
class ResearchAgent(Agent):
    """Researcher agent with research capabilities as methods."""
    
    def __init__(self, agent_id: str = "researcher", name: str = "Research Agent"):
        super().__init__(id=agent_id, name=name, agent_type="researcher")
        self.add_capabilities(["research", "data_collection", "fact_checking"])
    
    async def research(self, task: Task) -> TaskResult:
        """Research capability method."""
        topic = task.input_data.get("topic", "Unknown topic")
        print(f"🔍 Researching topic: {topic}")
        
        # Simulate research work
        await asyncio.sleep(2)
        
        research_data = {
            "topic": topic,
            "key_points": [
                f"Current trends in {topic}",
                f"Industry statistics for {topic}",
                f"Expert opinions on {topic}",
                f"Future outlook for {topic}"
            ],
            "sources": [
                f"Research paper on {topic}",
                f"Industry report: {topic} analysis",
                f"Expert interview about {topic}"
            ],
            "statistics": {
                "market_size": "$2.5B",
                "growth_rate": "15% YoY",
                "adoption_rate": "67%"
            }
        }
        
        return TaskResult.success_result(
            data=research_data,
            metadata={"research_time": 2, "sources_found": len(research_data["sources"])}
        )
    
    async def data_collection(self, task: Task) -> TaskResult:
        """Data collection capability method."""
        return await self.research(task)  # Same implementation for now
    
    async def fact_checking(self, task: Task) -> TaskResult:
        """Fact checking capability method."""
        content = task.input_data.get("content", "")
        print(f"✅ Fact-checking content...")
        await asyncio.sleep(1)
        
        return TaskResult.success_result(
            data={"verified": True, "accuracy_score": 95},
            metadata={"fact_check_time": 1}
        )


class WriterAgent(Agent):
    """Writer agent with writing capabilities as methods."""
    
    def __init__(self, agent_id: str = "writer", name: str = "Writer Agent"):
        super().__init__(id=agent_id, name=name, agent_type="writer")
        self.add_capabilities(["writing", "content_creation", "storytelling", "rewriting"])
    
    async def writing(self, task: Task) -> TaskResult:
        """Writing capability method using DSPy."""
        return await dspy_writing_handler(task)
    
    async def content_creation(self, task: Task) -> TaskResult:
        """Content creation capability method."""
        return await self.writing(task)  # Same as writing for now
    
    async def storytelling(self, task: Task) -> TaskResult:
        """Storytelling capability method."""
        return await self.writing(task)  # Same as writing for now
    
    async def rewriting(self, task: Task) -> TaskResult:
        """Rewriting capability method."""
        topic = task.input_data.get("topic", "Unknown topic")
        print(f"🔄 Rewriting blog post about: {topic}")
        # Mark as rewrite for the DSPy handler
        task.input_data["is_rewrite"] = True
        return await dspy_writing_handler(task)


class EditorAgent(Agent):
    """Editor agent with editing capabilities as methods."""
    
    def __init__(self, agent_id: str = "editor", name: str = "Editor Agent"):
        super().__init__(id=agent_id, name=name, agent_type="editor", max_concurrent_tasks=2)
        self.add_capabilities(["editing", "proofreading", "quality_assessment", "review"])
    
    async def editing(self, task: Task) -> TaskResult:
        """Editing capability method."""
        blog_post = task.input_data.get("blog_post", {})
        topic = blog_post.get("title", "Unknown blog post")
        
        print(f"📝 Editing and reviewing: {topic}")
        
        # Simulate editing work
        await asyncio.sleep(2)
        
        # Quality assessment
        quality_score = 8.5  # Mock quality score out of 10
        needs_rewrite = quality_score < 7.0
        
        if needs_rewrite:
            feedback = {
                "approved": False,
                "quality_score": quality_score,
                "feedback": [
                    "The introduction needs more compelling hook",
                    "Add more concrete examples in section 2",
                    "Conclusion should be more actionable"
                ],
                "suggestions": [
                    "Consider adding industry case studies",
                    "Include more recent statistics",
                    "Strengthen the call-to-action"
                ]
            }
            print(f"❌ Blog post needs revision (Quality Score: {quality_score}/10)")
            
            return TaskResult.success_result(
                data=feedback,
                metadata={"editing_time": 2, "needs_revision": True}
            )
        else:
            # Approved - apply final edits
            edited_post = blog_post.copy()
            edited_post.update({
                "status": "approved",
                "editor_notes": "Well-structured post with clear flow and good research backing",
                "final_word_count": blog_post.get("word_count", 0) + 50,  # Minor additions
                "quality_score": quality_score
            })
            
            print(f"✅ Blog post approved! (Quality Score: {quality_score}/10)")
            
            return TaskResult.success_result(
                data=edited_post,
                metadata={"editing_time": 2, "approved": True}
            )
    
    async def proofreading(self, task: Task) -> TaskResult:
        """Proofreading capability method."""
        return await self.editing(task)  # Same implementation for now
    
    async def quality_assessment(self, task: Task) -> TaskResult:
        """Quality assessment capability method."""
        return await self.editing(task)  # Same implementation for now
    
    async def review(self, task: Task) -> TaskResult:
        """Review capability method."""
        return await self.editing(task)  # Same implementation for now


class TeamLeadAgent(Agent):
    """Team lead agent with coordination capabilities as methods."""
    
    def __init__(self, agent_id: str = "team_lead", name: str = "Team Lead Agent"):
        super().__init__(id=agent_id, name=name, agent_type="lead", max_concurrent_tasks=5)
        self.add_capabilities(["coordination", "planning", "content_strategy", "blog_writing"])
    
    async def coordination(self, task: Task) -> TaskResult:
        """Coordination capability method."""
        return await self._coordinate_workflow(task)
    
    async def planning(self, task: Task) -> TaskResult:
        """Planning capability method."""
        return await self._coordinate_workflow(task)
    
    async def content_strategy(self, task: Task) -> TaskResult:
        """Content strategy capability method."""
        return await self._coordinate_workflow(task)
    
    async def blog_writing(self, task: Task) -> TaskResult:
        """High-level blog writing capability method."""
        return await self._coordinate_workflow(task)
    
    async def _coordinate_workflow(self, task: Task) -> TaskResult:
        """Internal workflow coordination method."""
        topic = task.input_data.get("topic", "Unknown topic")
        print(f"🎯 Team Lead coordinating complete blog writing for: {topic}")
        
        try:
            # Simulate the complete workflow coordination
            print("   📋 Planning blog writing workflow...")
            await asyncio.sleep(1)
            
            print("   🔍 Step 1: Research phase")
            research_result = await self._simulate_research_coordination(task)
            
            print("   ✍️  Step 2: Writing phase")  
            writing_result = await self._simulate_writing_coordination(task, research_result)
            
            print("   📝 Step 3: Editing and review phase")
            final_result = await self._simulate_editing_coordination(task, writing_result)
            
            return TaskResult.success_result(
                data={
                    "blog_post": final_result,
                    "workflow_completed": True,
                    "phases_completed": ["research", "writing", "editing"],
                    "quality_score": 8.5,
                    "topic": topic
                },
                metadata={
                    "coordination_time": 3,
                    "total_phases": 3,
                    "autonomous_execution": True
                }
            )
        except Exception as e:
            print(f"   ❌ Coordination failed: {str(e)}")
            return TaskResult.failure_result(
                error_message=f"Blog writing coordination failed: {str(e)}",
                metadata={"coordination_time": 1, "failed_phase": "planning"}
            )
    
    async def _simulate_research_coordination(self, task: Task) -> dict:
        """Simulate coordination of research phase."""
        topic = task.input_data.get("topic", "Unknown topic")
        print(f"     🔍 Coordinating research on {topic}...")
        await asyncio.sleep(1)
        
        return {
            "topic": topic,
            "key_points": [
                f"Current trends and developments in {topic}",
                f"Industry statistics and market analysis for {topic}",
                f"Expert opinions and thought leadership on {topic}",
                f"Future predictions and implications of {topic}"
            ],
            "sources": [
                f"Leading research paper: {topic} in Practice",
                f"Industry report: The Future of {topic}",
                f"Expert interview: {topic} Innovations"
            ],
            "research_quality": "comprehensive"
        }
    
    async def _simulate_writing_coordination(self, task: Task, research_data: dict) -> dict:
        """Simulate coordination of writing phase."""
        topic = research_data.get("topic", "Unknown topic")
        print(f"     ✍️  Coordinating blog post writing for {topic}...")
        await asyncio.sleep(2)
        
        return {
            "title": f"The Complete Guide to {topic}: Trends, Insights, and Future Outlook",
            "introduction": f"In today's rapidly evolving landscape, {topic} has emerged as a critical factor...",
            "sections": [
                {
                    "heading": f"Understanding {topic}",
                    "content": f"To fully grasp the impact of {topic}, we must first examine..."
                },
                {
                    "heading": "Current Market Trends",
                    "content": f"Recent analysis shows that {topic} is experiencing unprecedented growth..."
                },
                {
                    "heading": "Future Implications", 
                    "content": f"Looking ahead, {topic} is poised to reshape the industry in several ways..."
                }
            ],
            "conclusion": f"As we've explored, {topic} represents both opportunities and challenges...",
            "word_count": 2100,
            "writing_quality": "high",
            "research_integration": "comprehensive"
        }
    
    async def _simulate_editing_coordination(self, task: Task, blog_post: dict) -> dict:
        """Simulate coordination of editing and review phase."""
        title = blog_post.get("title", "Unknown blog post")
        print(f"     📝 Coordinating editing and review for: {title}")
        await asyncio.sleep(1)
        
        # Simulate quality assessment
        quality_score = 8.7  # High quality simulation
        
        if quality_score >= 8.0:
            print("     ✅ Blog post approved after review!")
            final_post = blog_post.copy()
            final_post.update({
                "status": "approved",
                "editor_notes": "Excellent structure, comprehensive research integration, engaging writing style",
                "final_word_count": blog_post.get("word_count", 2100) + 50,
                "quality_score": quality_score,
                "seo_optimized": True,
                "ready_for_publication": True
            })
            return final_post
        else:
            print("     🔄 Blog post needs revision...")
            return blog_post


# Legacy task handlers (kept for backward compatibility if needed)
async def research_handler(task: Task) -> TaskResult:
    """Handle research tasks for blog writing."""
    topic = task.input_data.get("topic", "Unknown topic")
    print(f"🔍 Researching topic: {topic}")
    
    # Simulate research work
    await asyncio.sleep(2)
    
    # Mock research results
    research_data = {
        "topic": topic,
        "key_points": [
            f"Current trends in {topic}",
            f"Industry statistics for {topic}",
            f"Expert opinions on {topic}",
            f"Future outlook for {topic}"
        ],
        "sources": [
            f"Research paper on {topic}",
            f"Industry report: {topic} analysis",
            f"Expert interview about {topic}"
        ],
        "statistics": {
            "market_size": "$2.5B",
            "growth_rate": "15% YoY",
            "adoption_rate": "67%"
        }
    }
    
    return TaskResult.success_result(
        data=research_data,
        metadata={"research_time": 2, "sources_found": len(research_data["sources"])}
    )


# Original writing handler (kept for reference)
async def writing_handler_original(task: Task) -> TaskResult:
    """Handle blog post writing tasks - original simulated version."""
    topic = task.input_data.get("topic", "Unknown topic")
    research_data = task.input_data.get("research_data", {})
    is_rewrite = task.input_data.get("is_rewrite", False)
    
    action = "Rewriting" if is_rewrite else "Writing"
    print(f"✍️ {action} blog post about: {topic}")
    
    # Simulate writing work
    await asyncio.sleep(3)
    
    # Use research data to create blog post
    key_points = research_data.get("key_points", [f"Information about {topic}"])
    sources = research_data.get("sources", [])
    
    blog_post = {
        "title": f"The Complete Guide to {topic}",
        "introduction": f"In today's rapidly evolving landscape, {topic} has become increasingly important...",
        "main_sections": [
            {
                "heading": f"Understanding {topic}",
                "content": f"Let's explore what {topic} really means and why it matters..."
            },
            {
                "heading": "Current Trends",
                "content": f"Based on our research, here are the key trends: {', '.join(key_points[:2])}"
            },
            {
                "heading": "Future Outlook",
                "content": f"Looking ahead, {topic} is expected to continue growing..."
            }
        ],
        "conclusion": f"As we've seen, {topic} presents both opportunities and challenges...",
        "word_count": 1500,
        "references": sources,
        "is_rewrite": is_rewrite
    }
    
    return TaskResult.success_result(
        data=blog_post,
        metadata={"writing_time": 3, "word_count": 1500, "revision": 1 if is_rewrite else 0}
    )


# New DSPy-powered writing handler (drop-in replacement)
async def writing_handler(task: Task) -> TaskResult:
    """
    Handle blog post writing tasks using DSPy modules.
    
    This is a drop-in replacement for the original writing_handler that uses
    DSPy for actual content generation instead of simulation.
    
    To switch between implementations:
    - Use writing_handler (this function) for DSPy-powered generation
    - Use writing_handler_original for the simulated version
    - Use dspy_writing_handler_simplified for single-step generation
    """
    return await dspy_writing_handler(task)


async def editing_handler(task: Task) -> TaskResult:
    """Handle blog post editing and review tasks."""
    blog_post = task.input_data.get("blog_post", {})
    topic = blog_post.get("title", "Unknown blog post")
    
    print(f"📝 Editing and reviewing: {topic}")
    
    # Simulate editing work
    await asyncio.sleep(2)
    
    # Quality assessment
    quality_score = 8.5  # Mock quality score out of 10
    needs_rewrite = quality_score < 7.0
    
    if needs_rewrite:
        feedback = {
            "approved": False,
            "quality_score": quality_score,
            "feedback": [
                "The introduction needs more compelling hook",
                "Add more concrete examples in section 2",
                "Conclusion should be more actionable"
            ],
            "suggestions": [
                "Consider adding industry case studies",
                "Include more recent statistics",
                "Strengthen the call-to-action"
            ]
        }
        print(f"❌ Blog post needs revision (Quality Score: {quality_score}/10)")
        
        return TaskResult.success_result(
            data=feedback,
            metadata={"editing_time": 2, "needs_revision": True}
        )
    else:
        # Approved - apply final edits
        edited_post = blog_post.copy()
        edited_post.update({
            "status": "approved",
            "editor_notes": "Well-structured post with clear flow and good research backing",
            "final_word_count": blog_post.get("word_count", 0) + 50,  # Minor additions
            "quality_score": quality_score
        })
        
        print(f"✅ Blog post approved! (Quality Score: {quality_score}/10)")
        
        return TaskResult.success_result(
            data=edited_post,
            metadata={"editing_time": 2, "approved": True}
        )


async def coordination_handler(task: Task) -> TaskResult:
    """
    High-level blog writing coordination handler.
    
    This handler orchestrates the complete blog writing workflow:
    1. Plans the work breakdown
    2. Coordinates with team members to execute subtasks
    3. Manages quality control and iterations
    4. Delivers final blog post
    """
    topic = task.input_data.get("topic", "Unknown topic")
    print(f"🎯 Team Lead coordinating complete blog writing for: {topic}")
    
    try:
        # Get team context from task metadata (workspace will provide this)
        workspace = task.metadata.get("workspace")  # Will be injected by the framework
        team = task.metadata.get("team")  # Will be injected by the framework
        
        if not workspace or not team:
            # Fallback for demo - simulate the coordination
            print("   📋 Planning blog writing workflow...")
            await asyncio.sleep(1)
            
            print("   🔍 Step 1: Research phase")
            research_result = await simulate_research_coordination(task)
            
            print("   ✍️  Step 2: Writing phase")  
            writing_result = await simulate_writing_coordination(task, research_result)
            
            print("   📝 Step 3: Editing and review phase")
            final_result = await simulate_editing_coordination(task, writing_result)
            
            return TaskResult.success_result(
                data={
                    "blog_post": final_result,
                    "workflow_completed": True,
                    "phases_completed": ["research", "writing", "editing"],
                    "quality_score": 8.5,
                    "topic": topic
                },
                metadata={
                    "coordination_time": 3,
                    "total_phases": 3,
                    "autonomous_execution": True
                }
            )
        else:
            # Real coordination with actual agents (future implementation)
            return await orchestrate_real_workflow(workspace, team, task)
            
    except Exception as e:
        print(f"   ❌ Coordination failed: {str(e)}")
        return TaskResult.failure_result(
            error_message=f"Blog writing coordination failed: {str(e)}",
            metadata={"coordination_time": 1, "failed_phase": "planning"}
        )


async def simulate_research_coordination(task: Task) -> dict:
    """Simulate coordination of research phase."""
    topic = task.input_data.get("topic", "Unknown topic")
    print(f"     🔍 Coordinating research on {topic}...")
    await asyncio.sleep(1)
    
    return {
        "topic": topic,
        "key_points": [
            f"Current trends and developments in {topic}",
            f"Industry statistics and market analysis for {topic}",
            f"Expert opinions and thought leadership on {topic}",
            f"Future predictions and implications of {topic}"
        ],
        "sources": [
            f"Leading research paper: {topic} in Practice",
            f"Industry report: The Future of {topic}",
            f"Expert interview: {topic} Innovations"
        ],
        "research_quality": "comprehensive"
    }


async def simulate_writing_coordination(task: Task, research_data: dict) -> dict:
    """Simulate coordination of writing phase."""
    topic = research_data.get("topic", "Unknown topic")
    print(f"     ✍️  Coordinating blog post writing for {topic}...")
    await asyncio.sleep(2)
    
    return {
        "title": f"The Complete Guide to {topic}: Trends, Insights, and Future Outlook",
        "introduction": f"In today's rapidly evolving landscape, {topic} has emerged as a critical factor...",
        "sections": [
            {
                "heading": f"Understanding {topic}",
                "content": f"To fully grasp the impact of {topic}, we must first examine..."
            },
            {
                "heading": "Current Market Trends",
                "content": f"Recent analysis shows that {topic} is experiencing unprecedented growth..."
            },
            {
                "heading": "Future Implications", 
                "content": f"Looking ahead, {topic} is poised to reshape the industry in several ways..."
            }
        ],
        "conclusion": f"As we've explored, {topic} represents both opportunities and challenges...",
        "word_count": 2100,
        "writing_quality": "high",
        "research_integration": "comprehensive"
    }


async def simulate_editing_coordination(task: Task, blog_post: dict) -> dict:
    """Simulate coordination of editing and review phase."""
    title = blog_post.get("title", "Unknown blog post")
    print(f"     📝 Coordinating editing and review for: {title}")
    await asyncio.sleep(1)
    
    # Simulate quality assessment
    quality_score = 8.7  # High quality simulation
    
    if quality_score >= 8.0:
        print("     ✅ Blog post approved after review!")
        final_post = blog_post.copy()
        final_post.update({
            "status": "approved",
            "editor_notes": "Excellent structure, comprehensive research integration, engaging writing style",
            "final_word_count": blog_post.get("word_count", 2100) + 50,
            "quality_score": quality_score,
            "seo_optimized": True,
            "ready_for_publication": True
        })
        return final_post
    else:
        print("     🔄 Blog post needs revision...")
        return blog_post


async def orchestrate_real_workflow(workspace, team, task: Task) -> TaskResult:
    """Future implementation for real agent coordination."""
    # This would implement actual agent-to-agent coordination
    # For now, fall back to simulation
    return await coordination_handler(task)


async def main():
    """
    This example creates a simple blog post writing team with an editor, a writer and researcher.
    
    Given a subject, the team will research the subject, write a blog post and edit it.
    If after the editor review the blog post is not satisfactory, the editor will request a rewrite from the writer.
    
    The team will use a RedisMessageBus to communicate.
    """
    print("📝 Starting Blog Writing Team Example with DSPy")
    print("=" * 55)
    
    # Configure DSPy for blog writing (loads from .env file automatically)
    try:
        print("\n🧠 Configuring DSPy for content generation...")
        configure_dspy_for_blog_writing()  # Uses environment variables from .env
    except Exception as e:
        print(f"⚠️  DSPy configuration failed: {e}")
        print("   Continuing with default configuration...")
    
    # Create framework instance with message bus (try Redis, fallback to in-memory)
    try:
        print("\n📡 Attempting to connect to Redis...")
        workspace = Workspace("BlogWriting", message_bus=RedisMessageBus("redis://localhost:6379"))
        async with workspace:
            print("✅ Framework started successfully")
            
            # Create blog writing team using enhanced Agent classes
            print("\n🏢 Creating Blog Writing Team with Enhanced Agents:")
            print("-" * 50)
            
            # Create agent instances with capabilities as methods
            team_lead = TeamLeadAgent("BlogTeamLead-001", "Blog Team Lead")
            researcher = ResearchAgent("Researcher-001", "Research Specialist")
            writer = WriterAgent("Writer-001", "Content Writer") 
            editor = EditorAgent("Editor-001", "Content Editor")
            
            # Add agents to workspace
            workspace._agents[team_lead.id] = team_lead
            workspace._agents[researcher.id] = researcher
            workspace._agents[writer.id] = writer
            workspace._agents[editor.id] = editor
            
            # Register with orchestration components
            for agent in [team_lead, researcher, writer, editor]:
                workspace.planner.register_agent(agent)
                workspace.monitor.register_agent(agent)
                agent.set_message_bus(workspace.message_bus)
                await agent.start()
            
            # Create team manually and add our enhanced agents
            from agentic_framework.core.team import Team
            blog_team = Team(
                name="Content Creation Team",
                description="Enhanced team for researching, writing, and editing blog posts",
                max_concurrent_tasks=5
            )
            
            # Add team members
            blog_team.add_member(team_lead.id, "lead")
            blog_team.add_member(researcher.id, "researcher") 
            blog_team.add_member(writer.id, "writer")
            blog_team.add_member(editor.id, "editor")
            
            # Set team lead
            blog_team.set_lead(team_lead.id)
            
            # Register agents with team
            for agent in [team_lead, researcher, writer, editor]:
                blog_team.register_agent(agent)
            
            # Register team with workspace
            workspace._teams[blog_team.id] = blog_team
            workspace.planner.register_team(blog_team)
            workspace.dispatcher.register_team(blog_team)
            workspace.monitor.register_team(blog_team)
            
            # Start team
            blog_team.set_message_bus(workspace.message_bus)
            await blog_team.start()
            
            # Show team status
            print(f"✅ Team created with {len(blog_team.members)} enhanced agents:")
            print(f"  - Lead: {team_lead.name} (capabilities: {[c.name for c in team_lead.capabilities]})")
            print(f"  - Researcher: {researcher.name} (capabilities: {[c.name for c in researcher.capabilities]})")
            print(f"  - Writer: {writer.name} (capabilities: {[c.name for c in writer.capabilities]})")
            print(f"  - Editor: {editor.name} (capabilities: {[c.name for c in editor.capabilities]})")
            
            # Execute autonomous blog writing workflow
            print("\n🚀 Starting Autonomous Blog Writing Workflow:")
            print("-" * 45)
            
            blog_topic = "Artificial Intelligence in Healthcare"
            print(f"Topic: {blog_topic}")
            print("\n📝 Creating single high-level blog writing task...")
            
            # Create one high-level blog writing task - team lead will handle the rest
            blog_writing_task = Task(
                title=f"Write Complete Blog Post: {blog_topic}",
                task_type="blog_writing",
                description=f"Plan and execute complete blog writing workflow for {blog_topic} including research, writing, and editing phases",
                input_data={"topic": blog_topic},
                required_capabilities=["blog_writing"],
                priority=TaskPriority.HIGH
            )
            
            print(f"\n📋 High-Level Task Created:")
            print(f"  - Title: {blog_writing_task.title}")
            print(f"  - Type: {blog_writing_task.task_type}")
            print(f"  - Capabilities required: {blog_writing_task.required_capabilities}")
            
            # Execute the high-level task - team lead will coordinate everything
            print(f"\n⚡ Executing autonomous blog writing task...")
            plan_id = await workspace.execute(blog_writing_task, blog_team.id)
            print(f"Execution plan created: {plan_id}")
            
            # Wait for completion - the team lead will handle all coordination
            print("\n⏳ Waiting for autonomous blog writing completion...")
            print("    (Team lead will coordinate research → writing → editing)")
            completed = await workspace.wait_for_completion(plan_id, timeout=30)
            
            if completed:
                print("\n🎉 Autonomous blog writing workflow completed!")
                print("✅ Team lead successfully coordinated the entire process")
            else:
                print("\n⚠️ Blog writing task did not complete within timeout")
            
            # Show final status
            final_status = workspace.get_system_status()
            print(f"\n📊 Final Results:")
            print(f"  - Tasks completed: {final_status['tasks']['completed']}")
            print(f"  - Tasks failed: {final_status['tasks']['failed']}")
            if final_status['average_task_duration'] > 0:
                print(f"  - Average duration: {final_status['average_task_duration']:.1f}s")
            
            print("\n✨ Blog Writing Team Example Completed!")
            print("=" * 50)
    except Exception as e:
        print(f"⚠️  Could not connect to Redis: {e}")
        print("🔄 Falling back to in-memory message bus...")
        
        try:
            workspace = Workspace("BlogWriting", message_bus=InMemoryMessageBus())
            async with workspace:
                print("✅ Workspace started successfully with in-memory message bus")
                
                # Create blog writing team using enhanced Agent classes  
                print("\n🏢 Creating Blog Writing Team with Enhanced Agents:")
                print("-" * 50)
                
                # Create agent instances with capabilities as methods
                team_lead = TeamLeadAgent("BlogTeamLead-001", "Blog Team Lead")
                researcher = ResearchAgent("Researcher-001", "Research Specialist")
                writer = WriterAgent("Writer-001", "Content Writer") 
                editor = EditorAgent("Editor-001", "Content Editor")
                
                # Add agents to workspace
                workspace._agents[team_lead.id] = team_lead
                workspace._agents[researcher.id] = researcher
                workspace._agents[writer.id] = writer
                workspace._agents[editor.id] = editor
                
                # Register with orchestration components
                for agent in [team_lead, researcher, writer, editor]:
                    workspace.planner.register_agent(agent)
                    workspace.monitor.register_agent(agent)
                    agent.set_message_bus(workspace.message_bus)
                    await agent.start()
                
                # Create team manually and add our enhanced agents
                from agentic_framework.core.team import Team
                blog_team = Team(
                    name="Content Creation Team",
                    description="Enhanced team for researching, writing, and editing blog posts",
                    max_concurrent_tasks=5
                )
                
                # Add team members
                blog_team.add_member(team_lead.id, "lead")
                blog_team.add_member(researcher.id, "researcher") 
                blog_team.add_member(writer.id, "writer")
                blog_team.add_member(editor.id, "editor")
                
                # Set team lead
                blog_team.set_lead(team_lead.id)
                
                # Register agents with team
                for agent in [team_lead, researcher, writer, editor]:
                    blog_team.register_agent(agent)
                
                # Register team with workspace
                workspace._teams[blog_team.id] = blog_team
                workspace.planner.register_team(blog_team)
                workspace.dispatcher.register_team(blog_team)
                workspace.monitor.register_team(blog_team)
                
                # Start team
                blog_team.set_message_bus(workspace.message_bus)
                await blog_team.start()
                
                # Show team status
                print(f"✅ Team created with {len(blog_team.members)} enhanced agents:")
                print(f"  - Lead: {team_lead.name} (capabilities: {[c.name for c in team_lead.capabilities]})")
                print(f"  - Researcher: {researcher.name} (capabilities: {[c.name for c in researcher.capabilities]})")
                print(f"  - Writer: {writer.name} (capabilities: {[c.name for c in writer.capabilities]})")
                print(f"  - Editor: {editor.name} (capabilities: {[c.name for c in editor.capabilities]})")
                
                # Execute autonomous blog writing workflow
                print("\n🚀 Starting Autonomous Blog Writing Workflow:")
                print("-" * 45)
                
                blog_topic = "Artificial Intelligence in Healthcare"
                print(f"Topic: {blog_topic}")
                print("\n📝 Creating single high-level blog writing task...")
                
                # Create one high-level blog writing task - team lead will handle the rest
                blog_writing_task = Task(
                    title=f"Write Complete Blog Post: {blog_topic}",
                    task_type="blog_writing",
                    description=f"Plan and execute complete blog writing workflow for {blog_topic} including research, writing, and editing phases",
                    input_data={"topic": blog_topic},
                    required_capabilities=["blog_writing"],
                    priority=TaskPriority.HIGH
                )
                
                print(f"\n📋 High-Level Task Created:")
                print(f"  - Title: {blog_writing_task.title}")
                print(f"  - Type: {blog_writing_task.task_type}")
                print(f"  - Capabilities required: {blog_writing_task.required_capabilities}")
                
                # Execute the high-level task - team lead will coordinate everything
                print(f"\n⚡ Executing autonomous blog writing task...")
                plan_id = await workspace.execute(blog_writing_task, blog_team.id)
                print(f"Execution plan created: {plan_id}")
                
                # Wait for completion - the team lead will handle all coordination
                print("\n⏳ Waiting for autonomous blog writing completion...")
                print("    (Team lead will coordinate research → writing → editing)")
                completed = await workspace.wait_for_completion(plan_id, timeout=30)
                
                if completed:
                    print("\n🎉 Autonomous blog writing workflow completed!")
                    print("✅ Team lead successfully coordinated the entire process")
                else:
                    print("\n⚠️ Blog writing task did not complete within timeout")
                
                # Show final status
                final_status = workspace.get_system_status()
                print(f"\n📊 Final Results:")
                print(f"  - Tasks completed: {final_status['tasks']['completed']}")
                print(f"  - Tasks failed: {final_status['tasks']['failed']}")
                if final_status['average_task_duration'] > 0:
                    print(f"  - Average duration: {final_status['average_task_duration']:.1f}s")
                
                print("\n✨ Blog Writing Team Example Completed!")
                print("=" * 50)
                
        except Exception as fallback_error:
            print(f"❌ Both Redis and in-memory fallback failed: {fallback_error}")
            print("🚨 Falling back to demo mode...")
            await demo_blog_writing_process()


async def demo_blog_writing_process():
    """Demo the blog writing process without Redis."""
    print("📚 Demo: Blog Writing Team Workflow")
    print("=" * 40)
    
    print("\n🎯 Blog Writing Process:")
    print("1. Researcher gathers information about the topic")
    print("2. Writer creates initial draft using research data")
    print("3. Editor reviews and assesses quality")
    print("4. If quality < 7/10, editor requests rewrite")
    print("5. Writer revises based on editor feedback")
    print("6. Process repeats until editor approves")
    
    print(f"\n👥 Team Roles:")
    print("• Researcher: Topic research, data collection, fact-checking")
    print("• Writer: Content creation, storytelling, draft writing")
    print("• Editor: Quality assessment, proofreading, final approval")
    print("• Team Lead: Workflow coordination, task planning")
    
    print(f"\n🔄 Quality Control Loop:")
    print("✅ Editor approves → Blog post published")
    print("❌ Editor rejects → Writer revises → Editor reviews again")
    
    print(f"\n📋 Example Topic: 'Artificial Intelligence in Healthcare'")
    print("Expected workflow:")
    print("  1. Research AI healthcare applications (2s)")
    print("  2. Write comprehensive blog post (3s)")
    print("  3. Editorial review and feedback (2s)")
    print("  4. Revision if needed (3s)")
    print("  5. Final approval")
    
    print(f"\n🚀 To run with full execution:")
    print("1. Start Redis: docker run -p 6379:6379 redis")
    print("2. Run: python -m agentic_framework.examples.my-team")


if __name__ == "__main__":
    asyncio.run(main())