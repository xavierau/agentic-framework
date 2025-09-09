# DSPy Blog Writing Module Refactor

This document describes the refactoring of the `writing_handler` function into a proper DSPy module system, following SOLID principles and DSPy best practices.

## Overview

The original `writing_handler` function has been refactored into a composable, async-enabled DSPy module system that:
- Uses actual LLM generation instead of simulation
- Follows SOLID principles with focused, single-responsibility modules
- Maintains async functionality within DSPy patterns
- Provides clean integration with the existing Task/TaskResult system
- Includes comprehensive error handling and robustness features

## Architecture

### Core DSPy Modules

#### 1. AsyncBlogPostWriter (Multi-Stage Approach)
```python
from agentic_framework.dspy_modules import AsyncBlogPostWriter

writer = AsyncBlogPostWriter()
blog_post = await writer.aforward(
    topic="AI in Healthcare",
    key_points=["diagnostic accuracy", "patient outcomes"],
    sources=["research paper", "industry report"],
    is_rewrite=False
)
```

**Components:**
- `BlogOutlineGenerator`: Creates blog structure and headings
- `BlogContentGenerator`: Generates content for each section
- `BlogIntroductionGenerator`: Creates engaging introductions
- `BlogConclusionGenerator`: Writes strong conclusions

**Benefits:**
- High-quality, structured output
- Parallel generation of sections for efficiency
- Granular control over each component
- Better error isolation and debugging

#### 2. SimplifiedBlogWriter (Single-Stage Approach)
```python
from agentic_framework.dspy_modules import SimplifiedBlogWriter

simple_writer = SimplifiedBlogWriter()
blog_post = await simple_writer.aforward(
    topic="Quantum Computing",
    key_points=["quantum supremacy", "error correction"],
    sources=["IBM research", "Nature journal"],
    is_rewrite=False
)
```

**Benefits:**
- Faster generation (single LLM call)
- Simpler implementation
- Good for shorter or less complex content
- Lower token usage

### Integration Layer

#### DSPyBlogWritingAdapter
Bridges DSPy modules with the existing Task/TaskResult system:

```python
from agentic_framework.dspy_modules import DSPyBlogWritingAdapter

# Create adapter with custom configuration
adapter = DSPyBlogWritingAdapter(
    use_simplified=False,
    lm_config={
        "model": "openai/gpt-4o-mini",
        "max_tokens": 2000,
        "temperature": 0.7
    }
)

# Handle task
result = await adapter.handle_writing_task(task)
```

#### Drop-in Handler Functions
```python
# Replace original writing_handler with DSPy version
from agentic_framework.dspy_modules import dspy_writing_handler

async def writing_handler(task: Task) -> TaskResult:
    return await dspy_writing_handler(task)

# Or use simplified version
from agentic_framework.dspy_modules import dspy_writing_handler_simplified

async def writing_handler(task: Task) -> TaskResult:
    return await dspy_writing_handler_simplified(task)
```

## Data Structures

### Pydantic Models

```python
class BlogSection(BaseModel):
    heading: str = Field(description="The heading for this section")
    content: str = Field(description="The detailed content for this section")

class BlogPostOutput(BaseModel):
    title: str = Field(description="The compelling title of the blog post")
    introduction: str = Field(description="An engaging introduction to the topic")
    main_sections: List[BlogSection] = Field(description="A list of main sections")
    conclusion: str = Field(description="A strong concluding summary")
    word_count: int = Field(description="Calculated word count of the generated blog post")
    references: List[str] = Field(description="A list of sources or references used")
    is_rewrite: bool = Field(description="True if this was a rewrite, false otherwise")
```

### DSPy Signatures

```python
class BlogOutlineSignature(dspy.Signature):
    """Generate a comprehensive outline for a blog post."""
    topic: str = dspy.InputField(desc="The main topic of the blog post")
    key_points: List[str] = dspy.InputField(desc="Key points and facts to include")
    is_rewrite: bool = dspy.InputField(desc="True if rewriting existing content")
    
    title: str = dspy.OutputField(desc="Compelling blog post title")
    introduction_outline: str = dspy.OutputField(desc="Summary of what the introduction should cover")
    section_headings: List[str] = dspy.OutputField(desc="3-4 main section headings")
    conclusion_outline: str = dspy.OutputField(desc="Summary of what the conclusion should cover")
```

## SOLID Principles Implementation

### Single Responsibility Principle (SRP)
- Each module has one clear purpose (outline generation, section content, etc.)
- Separation of DSPy logic from task system integration
- Focused signatures for specific tasks

### Open/Closed Principle (OCP)
- Easy to extend with new generator types
- Modular architecture allows adding new functionality without modifying existing code
- Pluggable LM configurations

### Liskov Substitution Principle (LSP)
- All generators follow consistent async interfaces
- Both writers implement the same `aforward` method signature
- Handlers can be swapped transparently

### Interface Segregation Principle (ISP)
- Focused signatures for each task type
- No large, monolithic interfaces
- Clean separation of concerns

### Dependency Inversion Principle (DIP)
- Depends on DSPy abstractions, not concrete implementations
- Configurable LM backends
- Injectable dependencies through factory patterns

## Usage Examples

### 1. Basic Integration (Existing Code)

Update your existing `my-team.py`:

```python
# Import the new DSPy modules
from agentic_framework.dspy_modules import (
    dspy_writing_handler,
    configure_dspy_for_blog_writing
)

# Configure DSPy (optional - uses defaults if not called)
configure_dspy_for_blog_writing(
    model="openai/gpt-4o-mini",
    max_tokens=2000,
    temperature=0.7
)

# Replace your writing handler
async def writing_handler(task: Task) -> TaskResult:
    return await dspy_writing_handler(task)
```

### 2. Custom Configuration

```python
from agentic_framework.dspy_modules import DSPyBlogWritingAdapter

# Create adapter with specific settings
adapter = DSPyBlogWritingAdapter(
    use_simplified=False,  # Use multi-stage approach
    lm_config={
        "model": "openai/gpt-4",  # Higher quality model
        "max_tokens": 3000,       # More tokens for longer content
        "temperature": 0.6        # More focused output
    }
)

async def premium_writing_handler(task: Task) -> TaskResult:
    return await adapter.handle_writing_task(task)
```

### 3. Direct Module Usage

```python
from agentic_framework.dspy_modules import AsyncBlogPostWriter, configure_dspy_for_blog_writing

# Configure DSPy
configure_dspy_for_blog_writing(model="openai/gpt-4o-mini")

# Use module directly
writer = AsyncBlogPostWriter()
blog_post = await writer.aforward(
    topic="Future of AI",
    key_points=["machine learning advances", "ethical considerations"],
    sources=["AI research papers", "industry reports"],
    is_rewrite=False
)

print(f"Generated: {blog_post.title}")
print(f"Word count: {blog_post.word_count}")
```

## Configuration

### Environment Setup

```bash
# Set your API key
export OPENAI_API_KEY="your_api_key_here"

# Install required dependencies
pip install dspy pydantic
```

### DSPy Configuration Options

```python
from agentic_framework.dspy_modules import configure_dspy_for_blog_writing

# Basic configuration
configure_dspy_for_blog_writing()

# Custom configuration
configure_dspy_for_blog_writing(
    model="openai/gpt-4o-mini",      # Model to use
    max_tokens=2000,                  # Token limit
    temperature=0.7,                  # Sampling temperature
    # Additional LM parameters...
)

# For other providers (example)
configure_dspy_for_blog_writing(
    model="anthropic/claude-3-sonnet",
    max_tokens=1500,
    temperature=0.6
)
```

## Error Handling

The modules include comprehensive error handling:

```python
async def writing_handler(task: Task) -> TaskResult:
    result = await dspy_writing_handler(task)
    
    if not result.success:
        print(f"Generation failed: {result.error}")
        print(f"Error metadata: {result.metadata}")
        
        # Fallback to original handler if needed
        return await writing_handler_original(task)
    
    return result
```

### Common Error Scenarios

1. **LLM API Errors**: Network issues, rate limits, API key problems
2. **Validation Errors**: LLM output doesn't match expected structure
3. **Empty Input**: Missing topic or research data
4. **Token Limits**: Content too long for model context window

## Performance Considerations

### Multi-Stage vs Single-Stage

| Approach | Speed | Quality | Token Usage | Use Case |
|----------|--------|---------|-------------|----------|
| AsyncBlogPostWriter | Slower | Higher | Higher | Long-form, high-quality content |
| SimplifiedBlogWriter | Faster | Good | Lower | Quick drafts, shorter content |

### Optimization Tips

1. **Parallel Execution**: AsyncBlogPostWriter generates sections in parallel
2. **Caching**: DSPy includes built-in caching for repeated requests
3. **Model Selection**: Choose appropriate models for quality/speed tradeoffs
4. **Token Management**: Monitor and optimize prompt lengths

## Testing

Run the demo script to test the implementation:

```bash
cd /Users/xavierau/Code/python/agentic-framework
python -m agentic_framework.examples.dspy_blog_demo
```

The demo includes:
- Direct DSPy module usage
- Task system integration
- Adapter usage examples
- Error handling scenarios

## Migration Guide

### Step 1: Install Dependencies
```bash
pip install dspy pydantic
```

### Step 2: Update Imports
```python
from agentic_framework.dspy_modules import (
    dspy_writing_handler,
    configure_dspy_for_blog_writing
)
```

### Step 3: Configure DSPy
```python
# Add to your main function
configure_dspy_for_blog_writing(
    model="openai/gpt-4o-mini",
    max_tokens=2000,
    temperature=0.7
)
```

### Step 4: Replace Handler
```python
# Original
async def writing_handler(task: Task) -> TaskResult:
    # ... simulation code ...

# New DSPy version
async def writing_handler(task: Task) -> TaskResult:
    return await dspy_writing_handler(task)
```

### Step 5: Test and Validate
```python
# Keep original as backup
async def writing_handler_original(task: Task) -> TaskResult:
    # ... original implementation ...

# Test new version
async def writing_handler(task: Task) -> TaskResult:
    try:
        return await dspy_writing_handler(task)
    except Exception as e:
        print(f"DSPy handler failed: {e}")
        return await writing_handler_original(task)
```

## Advanced Features

### Custom Signatures
Create custom signatures for specialized content:

```python
class TechnicalBlogSignature(dspy.Signature):
    """Generate technical blog content with code examples."""
    topic: str = dspy.InputField()
    technical_details: List[str] = dspy.InputField()
    code_examples: List[str] = dspy.InputField()
    
    title: str = dspy.OutputField()
    content: str = dspy.OutputField()
    code_snippets: List[str] = dspy.OutputField()
```

### Evaluation Metrics
Implement quality assessment:

```python
def evaluate_blog_quality(blog_post: BlogPostOutput, target_metrics: dict) -> dict:
    """Evaluate generated blog post quality."""
    return {
        "word_count_match": abs(blog_post.word_count - target_metrics.get("target_words", 1500)) < 200,
        "has_sections": len(blog_post.main_sections) >= 3,
        "has_references": len(blog_post.references) > 0,
        "content_coherence": True  # Would need actual evaluation logic
    }
```

## File Structure

```
agentic_framework/
├── dspy_modules/
│   ├── __init__.py              # Package exports
│   ├── blog_writing.py          # Core DSPy modules
│   └── task_adapters.py         # Task system integration
├── examples/
│   ├── my-team.py              # Updated with DSPy integration
│   └── dspy_blog_demo.py       # Comprehensive demo script
└── DSPY_BLOG_REFACTOR.md       # This documentation
```

## Conclusion

This refactor provides:

1. **Actual LLM Generation**: Replaces simulation with real content generation
2. **SOLID Architecture**: Clean, maintainable, extensible design  
3. **Async Support**: Maintains existing async patterns while adding DSPy capabilities
4. **Easy Integration**: Drop-in replacements for existing handlers
5. **Comprehensive Error Handling**: Robust production-ready implementation
6. **Performance Options**: Multiple approaches for different use cases

The implementation maintains backward compatibility while providing significant improvements in content quality, structure, and maintainability.