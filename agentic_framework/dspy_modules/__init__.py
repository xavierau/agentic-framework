"""
DSPy modules package for the agentic framework.

This package provides DSPy-based modules for various content generation tasks,
with clean integration into the existing task system.
"""

from .blog_writing import (
    AsyncBlogPostWriter,
    SimplifiedBlogWriter,
    BlogPostOutput,
    BlogSection,
    create_blog_writer,
)

from .task_adapters import (
    DSPyBlogWritingAdapter,
    dspy_writing_handler,
    dspy_writing_handler_simplified,
    configure_dspy_for_blog_writing,
    get_dspy_blog_adapter,
)

__all__ = [
    # Core blog writing modules
    'AsyncBlogPostWriter',
    'SimplifiedBlogWriter',
    'BlogPostOutput',
    'BlogSection',
    'create_blog_writer',
    
    # Task system integration
    'DSPyBlogWritingAdapter',
    'dspy_writing_handler',
    'dspy_writing_handler_simplified',
    'configure_dspy_for_blog_writing',
    'get_dspy_blog_adapter',
]