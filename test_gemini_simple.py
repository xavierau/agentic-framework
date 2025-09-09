#!/usr/bin/env python3
"""
Simple test script to verify Gemini API integration with DSPy blog writing.

Prerequisites:
1. Set GEMINI_API_KEY environment variable
2. Install dependencies: uv sync

Usage:
    # Set your Gemini API key
    export GEMINI_API_KEY="your-key-here"
    
    # Run the test
    uv run python test_gemini_simple.py
"""

import asyncio
import os
from agentic_framework.dspy_modules import configure_dspy_for_blog_writing, DSPyBlogWritingAdapter
from agentic_framework.core.task import Task, TaskResult


async def test_gemini_blog_writing():
    """Test Gemini API with DSPy blog writing."""
    print("🧪 Testing Gemini API with DSPy Blog Writing")
    print("=" * 50)
    
    # Check for API key
    if not os.getenv("GEMINI_API_KEY"):
        print("❌ GEMINI_API_KEY not found!")
        print("   Please set your Gemini API key:")
        print("   export GEMINI_API_KEY='your-key-here'")
        return
    
    print("✅ Found GEMINI_API_KEY")
    
    try:
        # Configure DSPy with Gemini
        print("\n🧠 Configuring DSPy with Gemini...")
        configure_dspy_for_blog_writing(
            model="gemini/gemini-2.0-flash-exp",
            max_tokens=1500,
            temperature=0.7
        )
        
        # Create adapter
        print("🔧 Creating DSPy blog writing adapter...")
        adapter = DSPyBlogWritingAdapter(use_simplified=True)
        
        # Create a simple test task
        print("\n📝 Creating test blog writing task...")
        task = Task(
            title="Test Blog Post - Python Programming",
            task_type="blog_writing",
            input_data={
                "topic": "Python Programming Best Practices",
                "research_data": {
                    "key_points": [
                        "Write clean, readable code",
                        "Use virtual environments",
                        "Follow PEP 8 style guidelines",
                        "Write comprehensive tests"
                    ],
                    "sources": [
                        "Python Official Documentation",
                        "PEP 8 Style Guide"
                    ]
                },
                "is_rewrite": False
            }
        )
        
        print(f"📋 Task created: {task.title}")
        print(f"🎯 Topic: {task.input_data['topic']}")
        
        # Execute the task
        print("\n⚡ Executing blog writing task with Gemini...")
        result: TaskResult = await adapter.handle_writing_task(task)
        
        # Display results
        if result.success:
            print("\n🎉 SUCCESS! Blog post generated with Gemini")
            print("=" * 50)
            
            blog_data = result.data
            print(f"📰 Title: {blog_data['title']}")
            print(f"📊 Word Count: {blog_data['word_count']}")
            print(f"📖 Sections: {len(blog_data['main_sections'])}")
            
            print(f"\n📝 Introduction:")
            print(blog_data['introduction'])
            
            print(f"\n📋 Main Sections:")
            for i, section in enumerate(blog_data['main_sections'], 1):
                print(f"{i}. {section['heading']}")
                preview = section['content'][:100] + "..." if len(section['content']) > 100 else section['content']
                print(f"   {preview}")
            
            print(f"\n🎯 Conclusion:")
            print(blog_data['conclusion'])
            
            if blog_data.get('references'):
                print(f"\n📚 References:")
                for ref in blog_data['references']:
                    print(f"  • {ref}")
            
            print(f"\n📊 Generation Metadata:")
            print(f"  • Generation time: {result.metadata.get('writing_time', 'N/A')}s")
            print(f"  • Model used: {result.metadata.get('model', 'Unknown')}")
            
        else:
            print(f"❌ FAILED: {result.error_message}")
            
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_gemini_blog_writing())