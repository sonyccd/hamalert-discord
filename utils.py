"""Utility functions and decorators."""
import functools
import logging
import time
from typing import Callable, TypeVar, Any


T = TypeVar('T')


def exponential_backoff(
    max_retries: int = -1,
    initial_delay: float = 1,
    max_delay: float = 60,
    exponential_base: float = 2,
    jitter: bool = False
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator for exponential backoff retry logic.
    
    Args:
        max_retries: Maximum number of retries (-1 for infinite)
        initial_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        exponential_base: Base for exponential backoff
        jitter: Add random jitter to delay
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            delay = initial_delay
            attempt = 0
            
            while max_retries == -1 or attempt < max_retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    attempt += 1
                    if max_retries != -1 and attempt >= max_retries:
                        raise
                    
                    logging.error(
                        f"{func.__name__} failed (attempt {attempt}): {e}"
                    )
                    
                    # Add jitter if requested
                    current_delay = delay
                    if jitter:
                        import random
                        current_delay *= (0.5 + random.random())
                    
                    logging.info(f"Retrying in {current_delay:.1f} seconds...")
                    time.sleep(current_delay)
                    
                    # Calculate next delay with exponential backoff
                    delay = min(delay * exponential_base, max_delay)
            
            raise Exception(f"Max retries ({max_retries}) exceeded")
        
        return wrapper
    return decorator


class RateLimiter:
    """Simple rate limiter for API calls."""
    
    def __init__(self, calls: int, period: float):
        """
        Initialize rate limiter.
        
        Args:
            calls: Number of calls allowed
            period: Time period in seconds
        """
        self.calls = calls
        self.period = period
        self.call_times: list[float] = []
    
    def __call__(self, func: Callable[..., T]) -> Callable[..., T]:
        """Decorator to rate limit function calls."""
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            now = time.time()
            
            # Remove old calls outside the period
            self.call_times = [
                t for t in self.call_times 
                if now - t < self.period
            ]
            
            # Check if we're at the limit
            if len(self.call_times) >= self.calls:
                sleep_time = self.period - (now - self.call_times[0])
                if sleep_time > 0:
                    logging.debug(f"Rate limit reached, sleeping {sleep_time:.1f}s")
                    time.sleep(sleep_time)
                    # Remove the oldest call after sleeping
                    self.call_times.pop(0)
            
            # Record this call
            self.call_times.append(now)
            
            return func(*args, **kwargs)
        
        return wrapper