"""Exception handling system for workflows and tasks."""

import time
import random
import asyncio
from typing import List, Dict, Any, Optional, Callable
from enum import Enum
from pydantic import BaseModel
import structlog

from ..events.event_types import (
    Event, ExceptionOccurred, RetryScheduled, CompensationTriggered
)


logger = structlog.get_logger()


class ExceptionStrategy(str, Enum):
    """Available exception handling strategies."""
    RETRY = "retry"
    COMPENSATE = "compensate"
    ESCALATE = "escalate"
    FAIL = "fail"


class BackoffStrategy(str, Enum):
    """Available backoff strategies for retries."""
    EXPONENTIAL = "exponential"
    LINEAR = "linear"
    FIXED = "fixed"


class RetryPolicy(BaseModel):
    """Configuration for retry behavior."""
    
    max_attempts: int = 3
    backoff_strategy: BackoffStrategy = BackoffStrategy.EXPONENTIAL
    initial_delay_ms: int = 1000
    max_delay_ms: int = 60000
    multiplier: float = 2.0
    jitter: bool = True
    
    def calculate_delay(self, attempt: int) -> int:
        """Calculate delay for a specific retry attempt."""
        if attempt <= 0:
            return 0
        
        if self.backoff_strategy == BackoffStrategy.FIXED:
            delay = self.initial_delay_ms
        elif self.backoff_strategy == BackoffStrategy.LINEAR:
            delay = self.initial_delay_ms * attempt
        else:  # EXPONENTIAL
            delay = self.initial_delay_ms * (self.multiplier ** (attempt - 1))
        
        # Cap at max delay
        delay = min(delay, self.max_delay_ms)
        
        # Add jitter if enabled
        if self.jitter:
            jitter_amount = delay * 0.1  # 10% jitter
            delay += random.uniform(-jitter_amount, jitter_amount)
        
        return int(max(0, delay))


class CompensationAction(BaseModel):
    """Specification for compensation actions (Saga pattern)."""
    
    step_id: str
    action_type: str  # Type of compensation action
    action_data: Dict[str, Any] = {}
    timeout_ms: int = 30000
    ignore_failures: bool = True  # Continue compensation even if this step fails
    order: int = 0  # Execution order (lower numbers execute first)


class ExceptionHandler(BaseModel):
    """Configuration for handling specific types of exceptions."""
    
    exception_types: List[str] = ["*"]  # * means all exceptions
    strategy: ExceptionStrategy = ExceptionStrategy.RETRY
    retry_policy: Optional[RetryPolicy] = None
    compensation_actions: List[CompensationAction] = []
    escalation_target: Optional[str] = None
    max_escalations: int = 3
    context_data: Dict[str, Any] = {}  # Additional context for the handler
    
    def matches_exception(self, exception_type: str) -> bool:
        """Check if this handler matches the given exception type."""
        return "*" in self.exception_types or exception_type in self.exception_types
    
    def get_retry_policy(self) -> RetryPolicy:
        """Get the retry policy, creating a default if none exists."""
        return self.retry_policy or RetryPolicy()


class ExceptionHandlingResult(BaseModel):
    """Result of exception handling."""
    
    strategy_used: ExceptionStrategy
    events_generated: List[Event] = []
    should_continue: bool = False
    delay_ms: int = 0
    next_action: Optional[str] = None
    metadata: Dict[str, Any] = {}


class ExceptionHandlingEngine:
    """Engine for processing exceptions and generating appropriate events."""
    
    def __init__(self):
        self._escalation_counts: Dict[str, int] = {}
        self._retry_counts: Dict[str, int] = {}
    
    async def handle_exception(
        self,
        exception: Exception,
        context_id: str,
        context_type: str,
        handlers: List[ExceptionHandler],
        operation_id: Optional[str] = None
    ) -> ExceptionHandlingResult:
        """Handle an exception using the provided handlers."""
        
        exception_type = type(exception).__name__
        
        # Log the exception
        logger.error(
            "Exception occurred",
            context_id=context_id,
            context_type=context_type,
            exception_type=exception_type,
            error_message=str(exception),
            operation_id=operation_id
        )
        
        # Generate exception event
        exception_event = ExceptionOccurred(
            context_id=context_id,
            context_type=context_type,
            exception_type=exception_type,
            error_message=str(exception),
            stack_trace=self._get_stack_trace(exception),
            metadata={"operation_id": operation_id} if operation_id else {}
        )
        
        events = [exception_event]
        
        # Find matching handler
        handler = self._find_matching_handler(exception_type, handlers)
        if not handler:
            # No handler found - default to fail strategy
            return ExceptionHandlingResult(
                strategy_used=ExceptionStrategy.FAIL,
                events_generated=events,
                should_continue=False
            )
        
        # Apply the handler strategy
        if handler.strategy == ExceptionStrategy.RETRY:
            return await self._handle_retry(
                context_id, context_type, handler, operation_id, events
            )
        elif handler.strategy == ExceptionStrategy.COMPENSATE:
            return await self._handle_compensate(
                context_id, context_type, handler, events
            )
        elif handler.strategy == ExceptionStrategy.ESCALATE:
            return await self._handle_escalate(
                context_id, context_type, handler, events
            )
        else:  # FAIL
            return ExceptionHandlingResult(
                strategy_used=ExceptionStrategy.FAIL,
                events_generated=events,
                should_continue=False
            )
    
    def _find_matching_handler(
        self, 
        exception_type: str, 
        handlers: List[ExceptionHandler]
    ) -> Optional[ExceptionHandler]:
        """Find the first handler that matches the exception type."""
        for handler in handlers:
            if handler.matches_exception(exception_type):
                return handler
        return None
    
    async def _handle_retry(
        self,
        context_id: str,
        context_type: str,
        handler: ExceptionHandler,
        operation_id: Optional[str],
        events: List[Event]
    ) -> ExceptionHandlingResult:
        """Handle retry strategy."""
        
        retry_key = f"{context_id}:{operation_id or 'default'}"
        current_attempts = self._retry_counts.get(retry_key, 0) + 1
        self._retry_counts[retry_key] = current_attempts
        
        retry_policy = handler.get_retry_policy()
        
        if current_attempts > retry_policy.max_attempts:
            logger.warning(
                "Max retry attempts exceeded",
                context_id=context_id,
                operation_id=operation_id,
                attempts=current_attempts,
                max_attempts=retry_policy.max_attempts
            )
            
            return ExceptionHandlingResult(
                strategy_used=ExceptionStrategy.FAIL,
                events_generated=events,
                should_continue=False,
                metadata={"reason": "max_retries_exceeded"}
            )
        
        # Calculate delay and schedule retry
        delay_ms = retry_policy.calculate_delay(current_attempts)
        
        retry_event = RetryScheduled(
            context_id=context_id,
            context_type=context_type,
            operation_id=operation_id or "default",
            attempt_number=current_attempts,
            delay_ms=delay_ms
        )
        
        events.append(retry_event)
        
        logger.info(
            "Retry scheduled",
            context_id=context_id,
            operation_id=operation_id,
            attempt=current_attempts,
            delay_ms=delay_ms
        )
        
        return ExceptionHandlingResult(
            strategy_used=ExceptionStrategy.RETRY,
            events_generated=events,
            should_continue=True,
            delay_ms=delay_ms,
            metadata={"attempt_number": current_attempts}
        )
    
    async def _handle_compensate(
        self,
        context_id: str,
        context_type: str,
        handler: ExceptionHandler,
        events: List[Event]
    ) -> ExceptionHandlingResult:
        """Handle compensation strategy (Saga pattern)."""
        
        if not handler.compensation_actions:
            logger.warning(
                "No compensation actions defined",
                context_id=context_id
            )
            return ExceptionHandlingResult(
                strategy_used=ExceptionStrategy.FAIL,
                events_generated=events,
                should_continue=False,
                metadata={"reason": "no_compensation_actions"}
            )
        
        # Sort compensation actions by order
        sorted_actions = sorted(handler.compensation_actions, key=lambda x: x.order)
        compensation_steps = [action.step_id for action in sorted_actions]
        
        compensation_event = CompensationTriggered(
            context_id=context_id,
            context_type=context_type,
            failed_step_id=context_id,  # Assuming context_id is the failed step
            compensation_steps=compensation_steps
        )
        
        events.append(compensation_event)
        
        logger.info(
            "Compensation triggered",
            context_id=context_id,
            compensation_steps=compensation_steps
        )
        
        return ExceptionHandlingResult(
            strategy_used=ExceptionStrategy.COMPENSATE,
            events_generated=events,
            should_continue=False,  # Original operation fails, but compensation runs
            metadata={"compensation_steps": compensation_steps}
        )
    
    async def _handle_escalate(
        self,
        context_id: str,
        context_type: str,
        handler: ExceptionHandler,
        events: List[Event]
    ) -> ExceptionHandlingResult:
        """Handle escalation strategy."""
        
        escalation_key = context_id
        current_escalations = self._escalation_counts.get(escalation_key, 0) + 1
        self._escalation_counts[escalation_key] = current_escalations
        
        if current_escalations > handler.max_escalations:
            logger.warning(
                "Max escalations exceeded",
                context_id=context_id,
                escalations=current_escalations,
                max_escalations=handler.max_escalations
            )
            
            return ExceptionHandlingResult(
                strategy_used=ExceptionStrategy.FAIL,
                events_generated=events,
                should_continue=False,
                metadata={"reason": "max_escalations_exceeded"}
            )
        
        # In a real implementation, you might send alerts, create tickets, etc.
        logger.warning(
            "Exception escalated",
            context_id=context_id,
            escalation_count=current_escalations,
            target=handler.escalation_target
        )
        
        return ExceptionHandlingResult(
            strategy_used=ExceptionStrategy.ESCALATE,
            events_generated=events,
            should_continue=False,
            metadata={
                "escalation_count": current_escalations,
                "escalation_target": handler.escalation_target
            }
        )
    
    def _get_stack_trace(self, exception: Exception) -> Optional[str]:
        """Get stack trace from exception if available."""
        import traceback
        try:
            return traceback.format_exc()
        except:
            return None
    
    def reset_retry_count(self, context_id: str, operation_id: Optional[str] = None) -> None:
        """Reset retry count for a specific operation."""
        retry_key = f"{context_id}:{operation_id or 'default'}"
        if retry_key in self._retry_counts:
            del self._retry_counts[retry_key]
    
    def reset_escalation_count(self, context_id: str) -> None:
        """Reset escalation count for a specific context."""
        if context_id in self._escalation_counts:
            del self._escalation_counts[context_id]
    
    def get_retry_count(self, context_id: str, operation_id: Optional[str] = None) -> int:
        """Get current retry count for an operation."""
        retry_key = f"{context_id}:{operation_id or 'default'}"
        return self._retry_counts.get(retry_key, 0)
    
    def get_escalation_count(self, context_id: str) -> int:
        """Get current escalation count for a context."""
        return self._escalation_counts.get(context_id, 0)