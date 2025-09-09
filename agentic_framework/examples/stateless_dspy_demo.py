"""
Stateless DSPy Blog Writing Demo for the Event-Driven Agentic Framework.

This demonstrates how to use DSPy modules in the new stateless, event-driven architecture:
- Events for task creation and completion
- State reconstruction from event logs
- Stateless worker processing
- Hybrid message bus (SQLite + Redis)
"""

import asyncio
import os
import json
from typing import Dict, Any, Optional
from uuid import uuid4
from pathlib import Path
import structlog

# Configure logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="ISO"),
        structlog.dev.ConsoleRenderer()
    ],
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True
)

logger = structlog.get_logger()

# Import the new event-driven components
from agentic_framework.messaging.hybrid_bus import HybridMessageBus
from agentic_framework.events.event_types import (
    TaskCreated, TaskCompleted, TaskFailed, AgentCreated, TeamCreated
)
from agentic_framework.events.aggregates import EventSourcedTask
from agentic_framework.workers.base_worker import StatelessWorker, WorkerConfig, WorkerResult
from agentic_framework.events.event_store import SQLiteEventStore
from agentic_framework.planning.exceptions import ExceptionHandler, RetryPolicy

# Try to import DSPy components (they may not exist in the new architecture)
try:
    from agentic_framework.dspy_modules import (
        AsyncBlogPostWriter, 
        SimplifiedBlogWriter,
        configure_dspy_for_blog_writing
    )
    DSPY_AVAILABLE = True
except ImportError:
    DSPY_AVAILABLE = False
    logger.warning("DSPy modules not available - creating mock implementations")


class MockBlogWriter:
    """Mock blog writer for demo purposes when DSPy is not available."""
    
    async def aforward(self, topic: str, key_points: list, sources: list, is_rewrite: bool = False):
        """Generate a mock blog post."""
        await asyncio.sleep(0.5)  # Simulate processing time
        
        class MockBlogPost:
            def model_dump(self):
                return {
                    "title": f"The Future of {topic}",
                    "introduction": f"This article explores the fascinating world of {topic} and its implications for the future.",
                    "main_sections": [
                        {
                            "heading": f"Understanding {topic}",
                            "content": f"To understand {topic}, we need to examine the key factors that drive innovation in this field. " + " ".join(key_points[:2])
                        },
                        {
                            "heading": f"Current Trends in {topic}",
                            "content": f"The current landscape of {topic} is rapidly evolving. " + " ".join(key_points[2:4])
                        },
                        {
                            "heading": f"Future Implications",
                            "content": f"Looking ahead, {topic} will continue to transform how we work and live. " + " ".join(key_points[4:] if len(key_points) > 4 else key_points[-1:])
                        }
                    ],
                    "conclusion": f"In conclusion, {topic} represents a significant opportunity for innovation and growth in the coming years.",
                    "word_count": 750,
                    "references": sources,
                    "is_rewrite": is_rewrite
                }
        
        return MockBlogPost()


class DSPyBlogWorker(StatelessWorker):
    """Stateless worker that handles DSPy blog writing tasks."""
    
    def __init__(self, config: WorkerConfig):
        super().__init__(config)
        
        # Initialize DSPy components
        if DSPY_AVAILABLE:
            self.async_writer = AsyncBlogPostWriter()
            self.simple_writer = SimplifiedBlogWriter()
        else:
            self.async_writer = MockBlogWriter()
            self.simple_writer = MockBlogWriter()
    
    async def process_event(self, event, state: Optional[EventSourcedTask]) -> list:
        """Process blog writing events."""
        
        if event.event_type == "TaskCreated" and state:
            return await self._handle_blog_writing_task(state)
        
        return []
    
    async def _handle_blog_writing_task(self, task: EventSourcedTask) -> list:
        """Handle a blog writing task."""
        
        if task.task_type != "blog_writing":
            return []
        
        logger.info(
            "Processing blog writing task",
            task_id=task.id,
            title=task.title,
            worker_id=self.config.worker_id
        )
        
        try:
            # Extract task data
            topic = task.input_data.get("topic", "")
            key_points = task.input_data.get("key_points", [])
            sources = task.input_data.get("sources", [])
            use_simple = task.input_data.get("use_simple_writer", False)
            is_rewrite = task.input_data.get("is_rewrite", False)
            
            if not topic:
                raise ValueError("Topic is required for blog writing")
            
            # Choose writer based on configuration
            writer = self.simple_writer if use_simple else self.async_writer
            
            logger.info(
                "Generating blog post",
                topic=topic,
                key_points_count=len(key_points),
                sources_count=len(sources),
                writer_type="simple" if use_simple else "advanced"
            )
            
            # Generate blog post
            start_time = asyncio.get_event_loop().time()
            blog_post = await writer.aforward(
                topic=topic,
                key_points=key_points,
                sources=sources,
                is_rewrite=is_rewrite
            )
            end_time = asyncio.get_event_loop().time()
            
            # Convert to dict
            blog_data = blog_post.model_dump()
            processing_time = end_time - start_time
            
            logger.info(
                "Blog post generated successfully",
                task_id=task.id,
                word_count=blog_data.get("word_count", 0),
                processing_time=f"{processing_time:.2f}s"
            )
            
            # Create task completion event
            task_completed = TaskCompleted(
                task_id=task.id,
                result={
                    "blog_post": blog_data,
                    "processing_time_seconds": processing_time,
                    "writer_type": "simple" if use_simple else "advanced",
                    "success": True
                },
                executor_id=f"dspy-blog-worker-{self.config.worker_id}"
            )
            
            return [task_completed]
            
        except Exception as e:
            logger.error(
                "Blog writing task failed",
                task_id=task.id,
                error=str(e)
            )
            
            # Create task failure event
            task_failed = TaskFailed(
                task_id=task.id,
                error_message=str(e),
                executor_id=f"dspy-blog-worker-{self.config.worker_id}"
            )
            
            return [task_failed]
    
    # StatelessWorker interface implementation
    
    async def _can_process_event(self, event, state) -> bool:
        """Check if this worker can process the event."""
        return (event.event_type == "TaskCreated" and 
                state and state.task_type == "blog_writing")
    
    async def _requires_state_reconstruction(self, event) -> bool:
        """Check if state reconstruction is needed."""
        return event.aggregate_type == "Task"
    
    async def _get_aggregate_class(self, aggregate_type: str):
        """Get the aggregate class for the given type."""
        if aggregate_type == "Task":
            return EventSourcedTask
        return None
    
    async def _requires_processing(self, event) -> bool:
        """Check if the event requires further processing."""
        return event.event_type in ["TaskCompleted", "TaskFailed"]
    
    async def _get_exception_handlers(self, event) -> list:
        """Get exception handlers for the event."""
        return [
            ExceptionHandler(
                exception_types=["*"],
                strategy="retry",
                retry_policy=RetryPolicy(max_attempts=2, initial_delay_ms=1000)
            )
        ]
    
    def get_supported_event_types(self) -> list:
        """Get supported event types."""
        return ["TaskCreated"]
    
    def get_worker_type(self) -> str:
        """Get worker type."""
        return "DSPyBlogWorker"


def print_blog_post(blog_data: Dict[str, Any], title: str = "Generated Blog Post"):
    """Pretty print a blog post for demo purposes."""
    print(f"\n{'=' * 60}")
    print(f" {title}")
    print('=' * 60)
    
    print(f"\n📰 TITLE: {blog_data['title']}")
    print(f"📊 Word Count: {blog_data['word_count']} words")
    print(f"🔄 Is Rewrite: {'Yes' if blog_data['is_rewrite'] else 'No'}")
    
    if blog_data.get('references'):
        print(f"📚 References: {len(blog_data['references'])} sources")
    
    print(f"\n📝 INTRODUCTION:")
    print(blog_data['introduction'])
    
    print(f"\n📋 MAIN SECTIONS ({len(blog_data['main_sections'])} sections):")
    for i, section in enumerate(blog_data['main_sections'], 1):
        print(f"\n  {i}. {section['heading']}")
        content = section['content']
        print(f"     {content[:200]}{'...' if len(content) > 200 else ''}")
    
    print(f"\n🎯 CONCLUSION:")
    print(blog_data['conclusion'])
    
    if blog_data.get('references'):
        print(f"\n📖 REFERENCES:")
        for ref in blog_data['references']:
            print(f"  • {ref}")


async def demo_event_driven_blog_writing():
    """Demo the event-driven blog writing system."""
    print("\n🚀 Event-Driven DSPy Blog Writing Demo")
    print("=" * 60)
    
    # Initialize the hybrid message bus
    bus = HybridMessageBus(
        sqlite_path="demo_events.db",
        redis_url="redis://localhost:6379"
    )
    
    try:
        await bus.connect()
        logger.info("Connected to hybrid message bus")
        
        # Create sample blog writing tasks
        tasks_data = [
            {
                "task_id": str(uuid4()),
                "title": "AI Healthcare Revolution",
                "topic": "Artificial Intelligence in Healthcare",
                "key_points": [
                    "AI-powered diagnostic tools improving accuracy",
                    "Predictive analytics for patient outcomes",
                    "Privacy concerns with medical data",
                    "Integration challenges with existing systems",
                    "Cost-benefit analysis of AI implementations"
                ],
                "sources": [
                    "Nature Medicine Journal - AI Diagnostics Study 2024",
                    "Healthcare AI Report - McKinsey 2024",
                    "HIMSS Healthcare IT Survey 2024"
                ],
                "use_simple_writer": False
            },
            {
                "task_id": str(uuid4()),
                "title": "Quantum Computing Breakthrough",
                "topic": "Recent Advances in Quantum Computing",
                "key_points": [
                    "Quantum supremacy achievements",
                    "Error correction improvements", 
                    "Commercial quantum services",
                    "Cryptography applications"
                ],
                "sources": [
                    "IBM Quantum Research 2024",
                    "Google Quantum AI Papers",
                    "Nature Quantum Information"
                ],
                "use_simple_writer": True
            }
        ]
        
        print(f"\n📝 Creating {len(tasks_data)} blog writing tasks...")
        
        # Create and dispatch task events
        task_events = []
        for task_data in tasks_data:
            task_event = TaskCreated(
                task_id=task_data["task_id"],
                title=task_data["title"],
                task_type="blog_writing",
                priority=2,
                required_capabilities=["dspy", "writing", "ai"],
                input_data={
                    "topic": task_data["topic"],
                    "key_points": task_data["key_points"],
                    "sources": task_data["sources"],
                    "use_simple_writer": task_data["use_simple_writer"]
                }
            )
            
            # Dispatch event to the system
            sequence_number = await bus.dispatch_event(task_event)
            task_events.append((task_event, sequence_number))
            
            print(f"✅ Task '{task_data['title']}' dispatched (seq: {sequence_number})")
        
        # Start a DSPy blog worker to process the tasks
        print(f"\n🤖 Starting DSPy blog worker...")
        
        worker_config = WorkerConfig(
            worker_id="dspy-blog-demo",
            event_store_path="demo_events.db",
            redis_url="redis://localhost:6379"
        )
        
        worker = DSPyBlogWorker(worker_config)
        await worker.initialize()
        
        # Process the events
        for task_event, seq_num in task_events:
            print(f"\n⚙️ Processing task: {task_event.payload['title']}")
            
            # Process the event (this simulates the worker pulling from queue)
            result = await worker.run_once(task_event)
            
            if result.success:
                print(f"✅ Task completed successfully!")
                print(f"📊 Generated {len(result.events_generated)} events")
                
                # Display the blog post if available
                for event in result.events_generated:
                    if event.event_type == "TaskCompleted":
                        blog_data = event.payload["result"]["blog_post"]
                        processing_time = event.payload["result"]["processing_time_seconds"]
                        writer_type = event.payload["result"]["writer_type"]
                        
                        print(f"⏱️ Processing time: {processing_time:.2f}s ({writer_type} writer)")
                        print_blog_post(blog_data, f"Result: {task_event.payload['title']}")
            else:
                print(f"❌ Task failed: {result.error_message}")
        
        await worker.shutdown()
        
        # Show event store statistics
        print(f"\n📊 Event Store Statistics:")
        status = await bus.get_status()
        print(f"   Next sequence number: {status['sqlite']['next_sequence']}")
        print(f"   Database: {status['sqlite']['database_path']}")
        
        # Demonstrate state reconstruction
        print(f"\n🔄 Demonstrating State Reconstruction:")
        task_id = tasks_data[0]["task_id"]
        
        reconstructed_task = await EventSourcedTask.reconstruct(task_id, bus.event_store)
        print(f"   Reconstructed task: {reconstructed_task.title}")
        print(f"   Status: {reconstructed_task.status}")
        print(f"   Version: {reconstructed_task.version}")
        if reconstructed_task.result:
            print(f"   Result keys: {list(reconstructed_task.result.keys())}")
        
    except Exception as e:
        logger.error("Demo failed", error=str(e))
        print(f"❌ Demo failed: {e}")
    
    finally:
        await bus.disconnect()


async def demo_workflow_integration():
    """Demo integrating DSPy with the workflow system."""
    print(f"\n🚀 Workflow Integration Demo")
    print("-" * 50)
    
    # Create a simple workflow definition for blog writing
    from agentic_framework.planning.workflow import (
        WorkflowDefinition, WorkflowStep, TaskSpec, WorkflowStore
    )
    
    # Define blog writing workflow
    workflow = WorkflowDefinition(
        name="blog_writing_workflow",
        description="Multi-step blog writing process",
        entry_point="research_step",
    )
    
    # Research step
    research_step = WorkflowStep(
        id="research_step",
        name="Research and Outline",
        type="task",
        task_spec=TaskSpec(
            task_type="research",
            required_capabilities=["research", "analysis"],
            input_mapping={"topic": "topic"},
            output_mapping={"research_data": "key_points"}
        ),
        on_success="writing_step"
    )
    
    # Writing step
    writing_step = WorkflowStep(
        id="writing_step",
        name="Blog Post Writing",
        type="task", 
        task_spec=TaskSpec(
            task_type="blog_writing",
            required_capabilities=["dspy", "writing"],
            input_mapping={"topic": "topic", "research_data": "key_points"}
        ),
        on_success="review_step"
    )
    
    # Review step
    review_step = WorkflowStep(
        id="review_step",
        name="Content Review",
        type="task",
        task_spec=TaskSpec(
            task_type="review",
            required_capabilities=["editing", "quality_assurance"]
        )
    )
    
    # Add steps to workflow
    workflow.add_step(research_step)
    workflow.add_step(writing_step) 
    workflow.add_step(review_step)
    
    # Validate workflow
    errors = workflow.validate_workflow()
    if errors:
        print(f"❌ Workflow validation failed:")
        for error in errors:
            print(f"   - {error}")
        return
    
    # Save workflow
    workflow_store = WorkflowStore("demo_events.db")
    workflow_store.save_workflow(workflow)
    
    print(f"✅ Created workflow: {workflow.name}")
    print(f"   Steps: {len(workflow.steps)}")
    print(f"   Entry point: {workflow.entry_point}")
    
    # Create a task that will use this workflow
    bus = HybridMessageBus(sqlite_path="demo_events.db")
    await bus.connect()
    
    try:
        workflow_task = TaskCreated(
            task_id=str(uuid4()),
            title="Sustainable Energy Blog Post",
            task_type="blog_writing_workflow",  # This will match our workflow
            priority=2,
            required_capabilities=["workflow", "research", "writing"],
            input_data={
                "topic": "Sustainable Energy Solutions for Smart Cities",
                "target_audience": "technology professionals",
                "word_count_target": 1200
            },
            workflow_id=workflow.id
        )
        
        sequence_number = await bus.dispatch_event(workflow_task)
        
        print(f"✅ Workflow task dispatched (seq: {sequence_number})")
        print(f"   Task ID: {workflow_task.aggregate_id}")
        print(f"   Workflow ID: {workflow.id}")
        
    finally:
        await bus.disconnect()


async def main():
    """Main demo function."""
    print("🎯 Stateless DSPy Blog Writing Demo")
    print("=" * 60)
    
    # Check environment
    if not DSPY_AVAILABLE:
        print("⚠️  DSPy modules not available - using mock implementations")
    
    if not os.getenv("OPENAI_API_KEY") and DSPY_AVAILABLE:
        print("⚠️  OPENAI_API_KEY not set - some features may not work")
    
    # Configure DSPy if available
    if DSPY_AVAILABLE:
        try:
            configure_dspy_for_blog_writing(
                model="openai/gpt-4o-mini",
                max_tokens=1500,
                temperature=0.7
            )
            print("✅ DSPy configured successfully")
        except Exception as e:
            print(f"❌ DSPy configuration failed: {e}")
    
    try:
        # Run demos
        await demo_event_driven_blog_writing()
        await demo_workflow_integration()
        
        print(f"\n🎉 All demos completed successfully!")
        
        print(f"\n💡 Key Features Demonstrated:")
        print("   ✅ Event-driven task creation and processing")
        print("   ✅ Stateless worker architecture") 
        print("   ✅ State reconstruction from events")
        print("   ✅ Hybrid message bus (SQLite + Redis)")
        print("   ✅ DSPy integration with event sourcing")
        print("   ✅ Workflow-based task orchestration")
        print("   ✅ Exception handling and retry logic")
        
        print(f"\n🔧 Architecture Benefits:")
        print("   • Complete statelessness - workers can terminate anytime")
        print("   • Full audit trail via event sourcing")
        print("   • Horizontal scaling with on-demand workers")
        print("   • Fault tolerance through event replay")
        print("   • Hybrid planning (deterministic + agentic)")
        
    except Exception as e:
        logger.error("Demo failed", error=str(e))
        print(f"❌ Demo failed: {e}")
        print("   This might be due to missing dependencies or configuration")


if __name__ == "__main__":
    asyncio.run(main())