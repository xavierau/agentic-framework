"""
DSPy modules for blog post writing and content generation.
Provides composable, async-enabled modules following SOLID principles.
"""
import asyncio
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import dspy


class BlogSection(BaseModel):
    """Represents a single section of a blog post."""
    heading: str = Field(description="The heading for this section")
    content: str = Field(description="The detailed content for this section")


class BlogPostOutput(BaseModel):
    """Structured output for a complete blog post."""
    title: str = Field(description="The compelling title of the blog post")
    introduction: str = Field(description="An engaging introduction to the topic")
    main_sections: List[BlogSection] = Field(description="A list of main sections with headings and content")
    conclusion: str = Field(description="A strong concluding summary of the blog post")
    word_count: int = Field(description="Calculated word count of the generated blog post")
    references: List[str] = Field(description="A list of sources or references used")
    is_rewrite: bool = Field(description="True if this was a rewrite, false otherwise")


class BlogOutlineSignature(dspy.Signature):
    """Generate a comprehensive outline for a blog post."""
    topic: str = dspy.InputField(desc="The main topic of the blog post")
    key_points: List[str] = dspy.InputField(desc="Key points and facts to include")
    is_rewrite: bool = dspy.InputField(desc="True if rewriting existing content")
    
    title: str = dspy.OutputField(desc="Compelling blog post title")
    introduction_outline: str = dspy.OutputField(desc="Summary of what the introduction should cover")
    section_headings: List[str] = dspy.OutputField(desc="3-4 main section headings")
    conclusion_outline: str = dspy.OutputField(desc="Summary of what the conclusion should cover")


class BlogSectionContentSignature(dspy.Signature):
    """Generate content for a specific blog section."""
    topic: str = dspy.InputField(desc="The main blog post topic")
    section_heading: str = dspy.InputField(desc="The heading for this specific section")
    key_points: List[str] = dspy.InputField(desc="Relevant key points to include")
    sources: List[str] = dspy.InputField(desc="Available sources for reference")
    
    section_content: str = dspy.OutputField(desc="Detailed, informative content for this section")


class BlogIntroductionSignature(dspy.Signature):
    """Generate an engaging introduction for the blog post."""
    topic: str = dspy.InputField(desc="The main blog post topic")
    introduction_outline: str = dspy.InputField(desc="What the introduction should cover")
    key_points: List[str] = dspy.InputField(desc="Key points to potentially reference")
    
    introduction: str = dspy.OutputField(desc="Engaging introduction that hooks the reader")


class BlogConclusionSignature(dspy.Signature):
    """Generate a strong conclusion for the blog post."""
    topic: str = dspy.InputField(desc="The main blog post topic")
    conclusion_outline: str = dspy.InputField(desc="What the conclusion should cover")
    key_points: List[str] = dspy.InputField(desc="Key points to summarize")
    
    conclusion: str = dspy.OutputField(desc="Strong conclusion that summarizes and provides closure")


class BlogOutlineGenerator(dspy.Module):
    """Module to generate blog post outline using Chain of Thought."""
    
    def __init__(self):
        super().__init__()
        self.generate_outline = dspy.ChainOfThought(BlogOutlineSignature)
    
    async def aforward(self, topic: str, key_points: List[str], is_rewrite: bool):
        """Generate blog post outline asynchronously."""
        return await self.generate_outline.acall(
            topic=topic,
            key_points=key_points,
            is_rewrite=is_rewrite
        )


class BlogContentGenerator(dspy.Module):
    """Module to generate individual blog sections."""
    
    def __init__(self):
        super().__init__()
        self.generate_section = dspy.ChainOfThought(BlogSectionContentSignature)
    
    async def aforward(self, topic: str, section_heading: str, key_points: List[str], sources: List[str]):
        """Generate section content asynchronously."""
        return await self.generate_section.acall(
            topic=topic,
            section_heading=section_heading,
            key_points=key_points,
            sources=sources
        )


class BlogIntroductionGenerator(dspy.Module):
    """Module to generate blog post introductions."""
    
    def __init__(self):
        super().__init__()
        self.generate_introduction = dspy.ChainOfThought(BlogIntroductionSignature)
    
    async def aforward(self, topic: str, introduction_outline: str, key_points: List[str]):
        """Generate introduction asynchronously."""
        return await self.generate_introduction.acall(
            topic=topic,
            introduction_outline=introduction_outline,
            key_points=key_points
        )


class BlogConclusionGenerator(dspy.Module):
    """Module to generate blog post conclusions."""
    
    def __init__(self):
        super().__init__()
        self.generate_conclusion = dspy.ChainOfThought(BlogConclusionSignature)
    
    async def aforward(self, topic: str, conclusion_outline: str, key_points: List[str]):
        """Generate conclusion asynchronously."""
        return await self.generate_conclusion.acall(
            topic=topic,
            conclusion_outline=conclusion_outline,
            key_points=key_points
        )


class AsyncBlogPostWriter(dspy.Module):
    """
    Comprehensive blog post writer using DSPy modules.
    
    Follows SOLID principles by composing smaller, focused modules:
    - Single Responsibility: Each sub-module handles one aspect
    - Open/Closed: Easy to extend with new generators
    - Liskov Substitution: All generators follow consistent interface
    - Interface Segregation: Focused signatures for each task
    - Dependency Inversion: Depends on DSPy abstractions
    """
    
    def __init__(self):
        super().__init__()
        self.outline_generator = BlogOutlineGenerator()
        self.content_generator = BlogContentGenerator()
        self.introduction_generator = BlogIntroductionGenerator()
        self.conclusion_generator = BlogConclusionGenerator()
    
    async def aforward(self, topic: str, key_points: List[str], sources: List[str], is_rewrite: bool) -> BlogPostOutput:
        """
        Generate a complete blog post asynchronously.
        
        Args:
            topic: The main topic for the blog post
            key_points: List of key information to include
            sources: List of source references
            is_rewrite: Whether this is a rewrite of existing content
            
        Returns:
            BlogPostOutput: Complete structured blog post
        """
        try:
            # Step 1: Generate outline
            outline_result = await self.outline_generator.aforward(
                topic=topic,
                key_points=key_points,
                is_rewrite=is_rewrite
            )
            
            # Step 2: Generate all content in parallel for efficiency
            tasks = []
            
            # Introduction task
            intro_task = self.introduction_generator.aforward(
                topic=topic,
                introduction_outline=outline_result.introduction_outline,
                key_points=key_points
            )
            tasks.append(intro_task)
            
            # Section content tasks
            section_tasks = []
            for heading in outline_result.section_headings:
                section_task = self.content_generator.aforward(
                    topic=topic,
                    section_heading=heading,
                    key_points=key_points,
                    sources=sources
                )
                section_tasks.append(section_task)
            
            # Conclusion task
            conclusion_task = self.conclusion_generator.aforward(
                topic=topic,
                conclusion_outline=outline_result.conclusion_outline,
                key_points=key_points
            )
            tasks.append(conclusion_task)
            
            # Execute introduction, all sections, and conclusion in parallel
            results = await asyncio.gather(
                intro_task,
                *section_tasks,
                conclusion_task,
                return_exceptions=True
            )
            
            # Handle any exceptions
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    raise result
            
            # Unpack results
            intro_result = results[0]
            section_results = results[1:-1]  # All middle results are sections
            conclusion_result = results[-1]
            
            # Step 3: Assemble the blog post
            main_sections = [
                BlogSection(heading=heading, content=section_result.section_content)
                for heading, section_result in zip(outline_result.section_headings, section_results)
            ]
            
            # Create the final blog post
            blog_post = BlogPostOutput(
                title=outline_result.title,
                introduction=intro_result.introduction,
                main_sections=main_sections,
                conclusion=conclusion_result.conclusion,
                word_count=0,  # Will be calculated
                references=sources,
                is_rewrite=is_rewrite
            )
            
            # Calculate actual word count
            blog_post.word_count = self._calculate_word_count(blog_post)
            
            return blog_post
            
        except Exception as e:
            # Log the error and re-raise with context
            print(f"Error in AsyncBlogPostWriter.aforward: {e}")
            raise RuntimeError(f"Failed to generate blog post for topic '{topic}': {e}")
    
    def _calculate_word_count(self, post: BlogPostOutput) -> int:
        """Calculate the total word count of the blog post."""
        count = 0
        count += len(post.title.split())
        count += len(post.introduction.split())
        count += len(post.conclusion.split())
        
        for section in post.main_sections:
            count += len(section.heading.split())
            count += len(section.content.split())
        
        return count


class SimplifiedBlogWriter(dspy.Module):
    """
    Alternative simplified blog writer for simpler use cases.
    Uses a single ChainOfThought for the entire blog post.
    """
    
    class SimpleBlogSignature(dspy.Signature):
        """Generate a complete blog post in one step."""
        topic: str = dspy.InputField(desc="The main topic of the blog post")
        key_points: List[str] = dspy.InputField(desc="Key points to include")
        sources: List[str] = dspy.InputField(desc="Sources to reference")
        is_rewrite: bool = dspy.InputField(desc="True if rewriting existing content")
        
        title: str = dspy.OutputField(desc="Blog post title")
        introduction: str = dspy.OutputField(desc="Engaging introduction")
        section1_heading: str = dspy.OutputField(desc="First main section heading")
        section1_content: str = dspy.OutputField(desc="First main section content")
        section2_heading: str = dspy.OutputField(desc="Second main section heading")
        section2_content: str = dspy.OutputField(desc="Second main section content")
        section3_heading: str = dspy.OutputField(desc="Third main section heading")
        section3_content: str = dspy.OutputField(desc="Third main section content")
        conclusion: str = dspy.OutputField(desc="Strong conclusion")
    
    def __init__(self):
        super().__init__()
        self.generate_blog = dspy.ChainOfThought(self.SimpleBlogSignature)
    
    async def aforward(self, topic: str, key_points: List[str], sources: List[str], is_rewrite: bool) -> BlogPostOutput:
        """Generate blog post using simplified single-step approach."""
        try:
            result = await self.generate_blog.acall(
                topic=topic,
                key_points=key_points,
                sources=sources,
                is_rewrite=is_rewrite
            )
            
            # Convert to structured output
            main_sections = [
                BlogSection(heading=result.section1_heading, content=result.section1_content),
                BlogSection(heading=result.section2_heading, content=result.section2_content),
                BlogSection(heading=result.section3_heading, content=result.section3_content),
            ]
            
            blog_post = BlogPostOutput(
                title=result.title,
                introduction=result.introduction,
                main_sections=main_sections,
                conclusion=result.conclusion,
                word_count=0,
                references=sources,
                is_rewrite=is_rewrite
            )
            
            # Calculate word count
            blog_post.word_count = self._calculate_word_count(blog_post)
            
            return blog_post
            
        except Exception as e:
            print(f"Error in SimplifiedBlogWriter.aforward: {e}")
            raise RuntimeError(f"Failed to generate blog post for topic '{topic}': {e}")
    
    def _calculate_word_count(self, post: BlogPostOutput) -> int:
        """Calculate the total word count of the blog post."""
        count = 0
        count += len(post.title.split())
        count += len(post.introduction.split())
        count += len(post.conclusion.split())
        
        for section in post.main_sections:
            count += len(section.heading.split())
            count += len(section.content.split())
        
        return count


def create_blog_writer(use_simplified: bool = False) -> dspy.Module:
    """
    Factory function to create appropriate blog writer module.
    
    Args:
        use_simplified: If True, returns SimplifiedBlogWriter, else AsyncBlogPostWriter
    
    Returns:
        Configured DSPy module for blog writing
    """
    if use_simplified:
        return SimplifiedBlogWriter()
    else:
        return AsyncBlogPostWriter()