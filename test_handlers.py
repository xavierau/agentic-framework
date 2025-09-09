#!/usr/bin/env python3
"""Test the blog writing task handlers directly."""

import asyncio
import sys
from pathlib import Path

# Add the agentic framework to path
sys.path.insert(0, str(Path(__file__).parent))

from agentic_framework import Task, TaskResult


async def research_handler(task: Task) -> TaskResult:
    """Handle research tasks for blog writing."""
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
        ]
    }
    
    print(f"✅ Research completed for {topic}")
    return TaskResult.success_result(
        data=research_data,
        metadata={"research_time": 2, "sources_found": len(research_data["sources"])}
    )


async def writing_handler(task: Task) -> TaskResult:
    """Handle blog post writing tasks."""
    topic = task.input_data.get("topic", "Unknown topic")
    research_data = task.input_data.get("research_data", {})
    
    print(f"✍️ Writing blog post about: {topic}")
    
    # Simulate writing work
    await asyncio.sleep(3)
    
    blog_post = {
        "title": f"The Complete Guide to {topic}",
        "word_count": 1500,
        "sections": ["Introduction", "Main Content", "Conclusion"]
    }
    
    print(f"✅ Writing completed for {topic}")
    return TaskResult.success_result(
        data=blog_post,
        metadata={"writing_time": 3, "word_count": 1500}
    )


async def editing_handler(task: Task) -> TaskResult:
    """Handle blog post editing and review tasks."""
    blog_post = task.input_data.get("blog_post", {})
    title = blog_post.get("title", "Unknown blog post")
    
    print(f"📝 Editing and reviewing: {title}")
    
    # Simulate editing work
    await asyncio.sleep(2)
    
    quality_score = 8.5
    edited_post = blog_post.copy()
    edited_post.update({
        "status": "approved",
        "quality_score": quality_score,
        "editor_notes": "Well-structured post with good flow"
    })
    
    print(f"✅ Editing completed with quality score: {quality_score}/10")
    return TaskResult.success_result(
        data=edited_post,
        metadata={"editing_time": 2, "approved": True}
    )


async def main():
    """Test the handlers directly."""
    print("🧪 Testing Blog Writing Task Handlers")
    print("=" * 40)
    
    topic = "Artificial Intelligence in Healthcare"
    
    # Test research handler
    print("\n1. Testing Research Handler:")
    research_task = Task(
        title=f"Research: {topic}",
        task_type="research",
        input_data={"topic": topic}
    )
    
    research_result = await research_handler(research_task)
    print(f"Research Success: {research_result.success}")
    
    # Test writing handler with research data
    print("\n2. Testing Writing Handler:")
    writing_task = Task(
        title=f"Write: {topic}",
        task_type="writing",
        input_data={
            "topic": topic,
            "research_data": research_result.data
        }
    )
    
    writing_result = await writing_handler(writing_task)
    print(f"Writing Success: {writing_result.success}")
    
    # Test editing handler
    print("\n3. Testing Editing Handler:")
    editing_task = Task(
        title=f"Edit: {topic}",
        task_type="editing",
        input_data={"blog_post": writing_result.data}
    )
    
    editing_result = await editing_handler(editing_task)
    print(f"Editing Success: {editing_result.success}")
    print(f"Quality Score: {editing_result.data.get('quality_score', 'N/A')}")
    print(f"Approved: {editing_result.metadata.get('approved', False)}")
    
    print("\n✅ All handlers tested successfully!")
    print("🎉 Blog writing workflow handlers are working correctly!")


if __name__ == "__main__":
    asyncio.run(main())