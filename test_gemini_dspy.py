#!/usr/bin/env python3
"""
Quick test script to verify DSPy + Gemini integration is working.
"""
import asyncio
import sys
from pathlib import Path

# Add the project root to path
sys.path.insert(0, str(Path(__file__).parent))

from agentic_framework.core.task import Task, TaskPriority
from agentic_framework.dspy_modules import dspy_writing_handler, configure_dspy_for_blog_writing

async def test_gemini_dspy():
    """Test the DSPy + Gemini integration with a simple task."""
    print("🧪 Testing DSPy + Gemini Integration")
    print("=" * 40)
    
    # Configure DSPy (uses .env file automatically)
    try:
        print("\n🧠 Configuring DSPy...")
        configure_dspy_for_blog_writing()
        print("✅ Configuration successful!")
    except Exception as e:
        print(f"❌ Configuration failed: {e}")
        return False
    
    # Create a test task
    print("\n📝 Creating test writing task...")
    test_task = Task(
        title="Test Blog Post: Python Async Programming",
        task_type="writing",
        description="Write a comprehensive blog post about Python async programming",
        input_data={
            "topic": "Python Async Programming",
            "research_data": {
                "key_points": [
                    "Understanding async/await syntax",
                    "Event loops and concurrency",
                    "Common async patterns",
                    "Performance benefits"
                ],
                "sources": [
                    "Python official documentation",
                    "Real Python async tutorial",
                    "FastAPI async guide"
                ]
            },
            "is_rewrite": False
        },
        required_capabilities=["writing"],
        priority=TaskPriority.HIGH
    )
    
    # Test the DSPy writing handler
    try:
        print("🚀 Executing DSPy writing handler...")
        print("   (This will make a real API call to Gemini)")
        
        result = await dspy_writing_handler(test_task)
        
        if result.status == "success":
            print("✅ Blog post generation successful!")
            print(f"\n📊 Results:")
            print(f"   Title: {result.data.get('title', 'N/A')}")
            print(f"   Word count: {result.data.get('word_count', 'N/A')}")
            print(f"   Sections: {len(result.data.get('main_sections', []))}")
            print(f"   Generation time: {result.metadata.get('writing_time', 'N/A')}s")
            
            # Show a preview of the content
            if 'introduction' in result.data:
                intro = result.data['introduction'][:200] + "..." if len(result.data['introduction']) > 200 else result.data['introduction']
                print(f"\n📖 Introduction preview:")
                print(f"   {intro}")
            
            return True
        else:
            print(f"❌ Generation failed: {result.data}")
            return False
            
    except Exception as e:
        print(f"❌ Error during generation: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_gemini_dspy())
    if success:
        print("\n🎉 Gemini + DSPy integration test PASSED!")
    else:
        print("\n💥 Gemini + DSPy integration test FAILED!")
        sys.exit(1)