"""
Adapter functions to integrate DSPy modules with the existing task system.
Provides clean separation between DSPy logic and task handling infrastructure.
"""
import asyncio
import os
from typing import Dict, Any, List, Optional
import dspy
from ..core.task import Task, TaskResult
from .blog_writing import AsyncBlogPostWriter, SimplifiedBlogWriter, BlogPostOutput

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # dotenv not installed, continue without loading .env
    pass


class DSPyBlogWritingAdapter:
    """
    Adapter class to bridge DSPy blog writing modules with the Task/TaskResult system.
    
    This adapter handles:
    - Input data transformation from Task to DSPy module format
    - DSPy module execution with proper error handling
    - Output transformation from DSPy results to TaskResult format
    - Performance timing and metadata collection
    """
    
    def __init__(self, use_simplified: bool = False, lm_config: Optional[Dict[str, Any]] = None):
        """
        Initialize the adapter with optional configuration.
        
        Args:
            use_simplified: Whether to use SimplifiedBlogWriter instead of AsyncBlogPostWriter
            lm_config: Configuration for the language model (e.g., {'model': 'gpt-4o-mini', 'max_tokens': 2000})
        """
        self.use_simplified = use_simplified
        self.writer = None
        self.lm_config = lm_config or {}
        
        # Initialize DSPy configuration if provided
        if lm_config:
            self._configure_dspy()
    
    def _configure_dspy(self):
        """Configure DSPy with the specified language model settings."""
        try:
            # Use environment variables as defaults, with Gemini fallbacks
            default_model = os.getenv('DSPY_DEFAULT_MODEL', 'gemini/gemini-2.5-flash')
            default_max_tokens = int(os.getenv('DSPY_MAX_TOKENS', '2000'))
            default_temperature = float(os.getenv('DSPY_TEMPERATURE', '0.7'))
            
            # Extract configuration parameters with env defaults
            model = self.lm_config.get('model', default_model)
            max_tokens = self.lm_config.get('max_tokens', default_max_tokens)
            temperature = self.lm_config.get('temperature', default_temperature)
            
            # Set API keys from environment if available
            if 'gemini' in model.lower() and os.getenv('GEMINI_API_KEY'):
                os.environ['GOOGLE_API_KEY'] = os.getenv('GEMINI_API_KEY')
            elif 'openai' in model.lower() and os.getenv('OPENAI_API_KEY'):
                os.environ['OPENAI_API_KEY'] = os.getenv('OPENAI_API_KEY')
            elif 'claude' in model.lower() or 'anthropic' in model.lower():
                if os.getenv('ANTHROPIC_API_KEY'):
                    os.environ['ANTHROPIC_API_KEY'] = os.getenv('ANTHROPIC_API_KEY')
            
            # Configure DSPy
            lm = dspy.LM(model=model, max_tokens=max_tokens, temperature=temperature)
            dspy.configure(lm=lm)
            
            print(f"DSPy configured with model: {model}")
            
        except Exception as e:
            print(f"Warning: Failed to configure DSPy: {e}")
            print("Using default DSPy configuration")
    
    def _get_writer(self):
        """Lazy initialization of the writer module."""
        if self.writer is None:
            if self.use_simplified:
                self.writer = SimplifiedBlogWriter()
            else:
                self.writer = AsyncBlogPostWriter()
        return self.writer
    
    def _extract_task_data(self, task: Task) -> tuple[str, List[str], List[str], bool]:
        """
        Extract and validate data from the Task object.
        
        Args:
            task: The input task containing blog writing parameters
            
        Returns:
            Tuple of (topic, key_points, sources, is_rewrite)
        """
        topic = task.input_data.get("topic", "Unknown topic")
        research_data = task.input_data.get("research_data", {})
        is_rewrite = task.input_data.get("is_rewrite", False)
        
        # Extract research data with defaults
        key_points = research_data.get("key_points", [f"General information about {topic}"])
        sources = research_data.get("sources", [])
        
        # Ensure key_points is a list
        if not isinstance(key_points, list):
            key_points = [str(key_points)]
        
        # Ensure sources is a list
        if not isinstance(sources, list):
            sources = [str(sources)] if sources else []
        
        return topic, key_points, sources, is_rewrite
    
    def _create_task_result(self, blog_post: BlogPostOutput, writing_time: float, topic: str) -> TaskResult:
        """
        Create a TaskResult from the DSPy blog post output.
        
        Args:
            blog_post: The generated blog post output
            writing_time: Time taken to generate the blog post
            topic: The original topic for metadata
            
        Returns:
            TaskResult with the blog post data and metadata
        """
        # Convert BlogPostOutput Pydantic model to dictionary
        blog_data = blog_post.model_dump()
        
        # Create metadata
        metadata = {
            "writing_time": writing_time,
            "word_count": blog_post.word_count,
            "revision": 1 if blog_post.is_rewrite else 0,
            "topic": topic,
            "sections_count": len(blog_post.main_sections),
            "references_count": len(blog_post.references),
            "dspy_module": "SimplifiedBlogWriter" if self.use_simplified else "AsyncBlogPostWriter"
        }
        
        return TaskResult.success_result(data=blog_data, metadata=metadata)
    
    async def handle_writing_task(self, task: Task) -> TaskResult:
        """
        Handle a blog writing task using DSPy modules.
        
        Args:
            task: The writing task to process
            
        Returns:
            TaskResult containing the generated blog post or error information
        """
        try:
            # Extract task data
            topic, key_points, sources, is_rewrite = self._extract_task_data(task)
            
            # Log the action
            action = "Rewriting" if is_rewrite else "Writing"
            print(f"✍️ {action} blog post about: {topic}")
            if key_points:
                print(f"   Key points: {len(key_points)} items")
            if sources:
                print(f"   Sources: {len(sources)} references")
            
            # Get the writer module
            writer = self._get_writer()
            
            # Measure execution time
            start_time = asyncio.get_event_loop().time()
            
            # Generate the blog post
            blog_post: BlogPostOutput = await writer.aforward(
                topic=topic,
                key_points=key_points,
                sources=sources,
                is_rewrite=is_rewrite
            )
            
            end_time = asyncio.get_event_loop().time()
            writing_time = round(end_time - start_time, 2)
            
            print(f"✅ Blog post generated successfully in {writing_time}s")
            print(f"   Title: {blog_post.title}")
            print(f"   Word count: {blog_post.word_count}")
            print(f"   Sections: {len(blog_post.main_sections)}")
            
            # Create and return TaskResult
            return self._create_task_result(blog_post, writing_time, topic)
            
        except Exception as e:
            print(f"❌ Error generating blog post: {e}")
            
            # Extract topic for error metadata
            topic = task.input_data.get("topic", "Unknown topic")
            is_rewrite = task.input_data.get("is_rewrite", False)
            
            return TaskResult.failure_result(
                error=f"Failed to generate blog post: {str(e)}",
                metadata={
                    "topic": topic,
                    "is_rewrite": is_rewrite,
                    "dspy_module": "SimplifiedBlogWriter" if self.use_simplified else "AsyncBlogPostWriter",
                    "error_type": type(e).__name__
                }
            )


# Global adapter instances for different configurations
_default_adapter = None
_simplified_adapter = None


def get_dspy_blog_adapter(use_simplified: bool = False, lm_config: Optional[Dict[str, Any]] = None) -> DSPyBlogWritingAdapter:
    """
    Get or create a DSPy blog writing adapter with caching.
    
    Args:
        use_simplified: Whether to use the simplified writer
        lm_config: Optional LM configuration
        
    Returns:
        Configured DSPyBlogWritingAdapter instance
    """
    global _default_adapter, _simplified_adapter
    
    if lm_config:
        # Always create new instance when custom config is provided
        return DSPyBlogWritingAdapter(use_simplified=use_simplified, lm_config=lm_config)
    
    # Use cached instances for default configurations
    if use_simplified:
        if _simplified_adapter is None:
            _simplified_adapter = DSPyBlogWritingAdapter(use_simplified=True)
        return _simplified_adapter
    else:
        if _default_adapter is None:
            _default_adapter = DSPyBlogWritingAdapter(use_simplified=False)
        return _default_adapter


async def dspy_writing_handler(task: Task) -> TaskResult:
    """
    Direct replacement for the original writing_handler function.
    
    This function provides a drop-in replacement that uses DSPy modules
    while maintaining the same interface as the original async function.
    
    Args:
        task: The writing task to process
        
    Returns:
        TaskResult containing the generated blog post
    """
    # Get the adapter (using default configuration)
    adapter = get_dspy_blog_adapter()
    
    # Handle the task
    return await adapter.handle_writing_task(task)


async def dspy_writing_handler_simplified(task: Task) -> TaskResult:
    """
    Alternative writing handler using the simplified blog writer.
    
    This version uses a single DSPy call instead of the multi-step approach,
    which may be faster but potentially less robust for complex content.
    
    Args:
        task: The writing task to process
        
    Returns:
        TaskResult containing the generated blog post
    """
    # Get the simplified adapter
    adapter = get_dspy_blog_adapter(use_simplified=True)
    
    # Handle the task
    return await adapter.handle_writing_task(task)


# Configuration function for easy setup
def configure_dspy_for_blog_writing(
    model: str = None,
    max_tokens: int = None,
    temperature: float = None,
    **kwargs
) -> None:
    """
    Configure DSPy for blog writing tasks.
    
    Automatically loads configuration from environment variables if available:
    - DSPY_DEFAULT_MODEL: Default model to use
    - DSPY_MAX_TOKENS: Maximum tokens for generation  
    - DSPY_TEMPERATURE: Sampling temperature
    - GEMINI_API_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY: API keys
    
    Args:
        model: The model identifier (e.g., "gemini/gemini-2.5-flash"). Defaults to env var or "gemini/gemini-2.5-flash"
        max_tokens: Maximum tokens for generation. Defaults to env var or 2000
        temperature: Sampling temperature. Defaults to env var or 0.7
        **kwargs: Additional LM configuration parameters
    """
    try:
        # Use environment variables as defaults, with Gemini fallbacks
        default_model = os.getenv('DSPY_DEFAULT_MODEL', 'gemini/gemini-2.5-flash')
        default_max_tokens = int(os.getenv('DSPY_MAX_TOKENS', '2000'))
        default_temperature = float(os.getenv('DSPY_TEMPERATURE', '0.7'))
        
        # Override with provided parameters
        final_model = model if model is not None else default_model
        final_max_tokens = max_tokens if max_tokens is not None else default_max_tokens
        final_temperature = temperature if temperature is not None else default_temperature
        
        lm_config = {
            'model': final_model,
            'max_tokens': final_max_tokens,
            'temperature': final_temperature,
            **kwargs
        }
        
        # Set API keys from environment if available
        if 'gemini' in final_model.lower() and os.getenv('GEMINI_API_KEY'):
            os.environ['GOOGLE_API_KEY'] = os.getenv('GEMINI_API_KEY')
        elif 'openai' in final_model.lower() and os.getenv('OPENAI_API_KEY'):
            os.environ['OPENAI_API_KEY'] = os.getenv('OPENAI_API_KEY') 
        elif 'claude' in final_model.lower() or 'anthropic' in final_model.lower():
            if os.getenv('ANTHROPIC_API_KEY'):
                os.environ['ANTHROPIC_API_KEY'] = os.getenv('ANTHROPIC_API_KEY')
        
        lm = dspy.LM(**lm_config)
        dspy.configure(lm=lm)
        
        print(f"✅ DSPy configured for blog writing:")
        print(f"   Model: {final_model}")
        print(f"   Max tokens: {final_max_tokens}")
        print(f"   Temperature: {final_temperature}")
        
        # Reset cached adapters to pick up new configuration
        global _default_adapter, _simplified_adapter
        _default_adapter = None
        _simplified_adapter = None
        
    except Exception as e:
        print(f"❌ Failed to configure DSPy: {e}")
        raise