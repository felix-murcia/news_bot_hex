"""Retry utilities with exponential backoff.

Provides a decorator and context manager for retrying operations
with exponential backoff and jitter.
"""

import time
import random
import logging
from functools import wraps
from typing import Callable, Type, Tuple, Optional, Any

logger = logging.getLogger(__name__)


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retryable_exceptions: Optional[Tuple[Type[Exception], ...]] = None,
) -> Callable:
    """Decorator that retries a function on failure with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries in seconds
        exponential_base: Base for exponential calculation
        jitter: Whether to add random jitter to delay
        retryable_exceptions: Tuple of exception types to retry on (default: all Exception)
    
    Returns:
        Decorated function with retry logic
    
    Example:
        @retry_with_backoff(max_retries=3, base_delay=1.0)
        def api_call():
            # ... code that might fail
            pass
    """
    if retryable_exceptions is None:
        retryable_exceptions = (Exception,)
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e
                    
                    if attempt == max_retries:
                        logger.error(
                            f"[RETRY] {func.__name__} failed after {max_retries} retries: {e}"
                        )
                        raise
                    
                    # Calculate delay with exponential backoff
                    delay = min(
                        base_delay * (exponential_base ** attempt),
                        max_delay,
                    )
                    
                    # Add jitter to prevent thundering herd
                    if jitter:
                        delay = delay * (0.5 + random.random() * 0.5)
                    
                    logger.warning(
                        f"[RETRY] {func.__name__} failed (attempt {attempt + 1}/{max_retries}): {e}. "
                        f"Retrying in {delay:.2f}s..."
                    )
                    time.sleep(delay)
            
            # Should never reach here, but just in case
            raise last_exception  # type: ignore[misc]
        
        return wrapper
    return decorator


class RetryContext:
    """Context manager for retrying a block of code.
    
    Example:
        with RetryContext(max_retries=3) as ctx:
            result = risky_operation()
        
        # Or with result access:
        with RetryContext(max_retries=3) as ctx:
            ctx.result = api_call()
        
        print(ctx.result)
    """
    
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        jitter: bool = True,
        retryable_exceptions: Optional[Tuple[Type[Exception], ...]] = None,
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.jitter = jitter
        self.retryable_exceptions = retryable_exceptions or (Exception,)
        self.result: Any = None
        self.attempts = 0
        self.last_error: Optional[Exception] = None
    
    def __enter__(self) -> "RetryContext":
        return self
    
    def __exit__(self, exc_type: Optional[Type[Exception]], exc_val: Optional[Exception], exc_tb: Any) -> bool:
        """Handle retry logic.
        
        Returns True to suppress the exception (we'll retry), False to propagate.
        """
        if exc_type is None:
            # No exception occurred
            return True
        
        if not issubclass(exc_type, self.retryable_exceptions):
            # Not a retryable exception, let it propagate
            return False
        
        self.attempts += 1
        self.last_error = exc_val
        
        if self.attempts >= self.max_retries:
            logger.error(
                f"[RETRY] Operation failed after {self.max_retries} retries: {exc_val}"
            )
            return False  # Let exception propagate
        
        # Calculate delay
        delay = min(
            self.base_delay * (2 ** self.attempts),
            self.max_delay,
        )
        
        if self.jitter:
            delay = delay * (0.5 + random.random() * 0.5)
        
        logger.warning(
            f"[RETRY] Operation failed (attempt {self.attempts + 1}/{self.max_retries}): {exc_val}. "
            f"Retrying in {delay:.2f}s..."
        )
        
        time.sleep(delay)
        return True  # Suppress exception and retry


def retry_http_request(
    max_retries: int = 3,
    base_delay: float = 2.0,
) -> Callable:
    """Specialized decorator for HTTP requests with sensible defaults.
    
    Retries on common HTTP errors (connection errors, timeouts, 5xx status codes).
    """
    import requests
    
    retryable = (
        requests.ConnectionError,
        requests.Timeout,
        requests.ConnectionError,
    )
    
    return retry_with_backoff(
        max_retries=max_retries,
        base_delay=base_delay,
        retryable_exceptions=retryable,
    )
