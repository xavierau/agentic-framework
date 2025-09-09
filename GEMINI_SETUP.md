# Gemini API Setup for DSPy Blog Writing

This guide shows how to configure the agentic framework to use Google's Gemini API for blog writing tasks.

## Prerequisites

1. **Get a Gemini API key**:
   - Visit [Google AI Studio](https://aistudio.google.com/app/apikey)
   - Create a new API key
   - Copy the key for use in your environment

2. **Install dependencies**:
   ```bash
   uv sync
   ```

## Configuration

### Method 1: Environment Variables (Recommended)

Set your API key as an environment variable:

```bash
# For current session
export GEMINI_API_KEY="your-gemini-api-key-here"

# Or add to your shell profile (~/.bashrc, ~/.zshrc, etc.)
echo 'export GEMINI_API_KEY="your-gemini-api-key-here"' >> ~/.zshrc
```

### Method 2: .env File

Create a `.env` file in the project root:

```env
GEMINI_API_KEY=your-gemini-api-key-here
DSPY_DEFAULT_MODEL=gemini/gemini-2.0-flash-exp
DSPY_MAX_TOKENS=2000
DSPY_TEMPERATURE=0.7
```

## Available Gemini Models

The framework supports these Gemini models:

- `gemini/gemini-2.0-flash-exp` - Latest experimental model (default)
- `gemini/gemini-2.5-flash` - Stable Flash model
- `gemini/gemini-1.5-pro` - Pro model for complex tasks
- `gemini/gemini-1.5-flash` - Fast model for simple tasks

## Usage Examples

### Quick Test

```bash
# Test Gemini integration
uv run python test_gemini_simple.py
```

### Full Demo with Gemini

```bash
# Run the complete DSPy blog demo with Gemini
uv run python -m agentic_framework.examples.dspy_blog_demo
```

### Programmatic Usage

```python
import asyncio
from agentic_framework.dspy_modules import configure_dspy_for_blog_writing, DSPyBlogWritingAdapter
from agentic_framework.core.task import Task

async def example_gemini_usage():
    # Configure with Gemini
    configure_dspy_for_blog_writing(
        model="gemini/gemini-2.0-flash-exp",
        max_tokens=2000,
        temperature=0.7
    )
    
    # Create adapter
    adapter = DSPyBlogWritingAdapter(use_simplified=False)
    
    # Create task
    task = Task(
        title="AI in Healthcare",
        task_type="blog_writing",
        input_data={
            "topic": "AI Applications in Modern Healthcare",
            "research_data": {
                "key_points": ["Medical imaging", "Drug discovery", "Patient care"],
                "sources": ["Medical Journal 2024"]
            }
        }
    )
    
    # Generate blog post
    result = await adapter.handle_writing_task(task)
    print(result.data['title'])

# Run example
asyncio.run(example_gemini_usage())
```

## Advanced Configuration

### Custom Model Parameters

```python
from agentic_framework.dspy_modules import DSPyBlogWritingAdapter

# Custom Gemini configuration
custom_config = {
    "model": "gemini/gemini-2.0-flash-exp",
    "max_tokens": 3000,
    "temperature": 0.8,
    "top_p": 0.9,
}

adapter = DSPyBlogWritingAdapter(
    use_simplified=False,
    lm_config=custom_config
)
```

### Workspace Integration

```python
from agentic_framework import Workspace
from agentic_framework.examples.dspy_blog_demo import DSPyBlogAgent

async def workspace_gemini_example():
    async with Workspace("GeminiWorkspace") as workspace:
        # Create Gemini-powered blog agent
        gemini_agent = DSPyBlogAgent(
            "GeminiWriter",
            use_simplified=False,
            lm_config={
                "model": "gemini/gemini-2.0-flash-exp",
                "max_tokens": 2000
            }
        )
        
        # Build team
        team = await workspace.team("AI Writing Team") \
            .with_agent_instance(gemini_agent) \
            .build()
        
        # Execute tasks...
```

## Troubleshooting

### Common Issues

1. **API Key Not Found**:
   ```
   ❌ GEMINI_API_KEY not found!
   ```
   - Ensure your API key is set correctly
   - Check spelling: `GEMINI_API_KEY` (not `GOOGLE_API_KEY`)

2. **Authentication Error**:
   ```
   Error 403: API key not valid
   ```
   - Verify your API key is active in Google AI Studio
   - Check if API key has proper permissions

3. **Rate Limiting**:
   ```
   Error 429: Too many requests
   ```
   - Reduce request frequency
   - Consider upgrading your Gemini API tier

4. **Model Not Found**:
   ```
   Error 404: Model not found
   ```
   - Check model name spelling
   - Verify model availability in your region

### Debug Mode

Enable verbose logging to troubleshoot:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Your DSPy code here...
```

## Performance Tips

1. **Use appropriate models**:
   - `gemini-2.0-flash-exp` for high-quality content
   - `gemini-2.5-flash` for faster, simpler tasks

2. **Optimize token usage**:
   - Set appropriate `max_tokens` limits
   - Use `use_simplified=True` for shorter content

3. **Handle rate limits**:
   - Implement exponential backoff
   - Use batch processing for multiple requests

## Cost Optimization

- **Gemini 2.0 Flash Exp**: Free tier available
- **Monitor usage** in Google AI Studio console
- **Use simplified writer** for lower token consumption
- **Set appropriate max_tokens** to avoid unnecessary generation

For more information, see the [Google AI documentation](https://ai.google.dev/docs).