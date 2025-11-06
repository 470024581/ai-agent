"""
Rate limiter utility module for API request limiting.

Implements sliding window rate limiting algorithm to prevent API abuse.
"""

import time
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from fastapi import Request, HTTPException
from functools import wraps
import logging

logger = logging.getLogger(__name__)

# Rate limit configuration
MAX_REQUESTS = 10  # Maximum requests allowed
WINDOW_MINUTES = 10  # Time window in minutes
WINDOW_SECONDS = WINDOW_MINUTES * 60  # Convert to seconds

# In-memory storage for rate limit data
# Structure: {ip_address: [timestamp1, timestamp2, ...]}
_rate_limit_store: Dict[str, List[float]] = {}

# Lock for thread-safe operations
_rate_limit_lock = asyncio.Lock()

# Background task for periodic cleanup
_cleanup_task: Optional[asyncio.Task] = None


def get_client_ip(request: Request) -> str:
    """
    Extract client IP address from request.
    Handles proxy scenarios by checking X-Forwarded-For header.
    
    Args:
        request: FastAPI Request object
        
    Returns:
        Client IP address as string
    """
    # Check for X-Forwarded-For header (for proxy/load balancer scenarios)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # X-Forwarded-For can contain multiple IPs, take the first one
        ip = forwarded_for.split(",")[0].strip()
        if ip:
            return ip
    
    # Fallback to direct client IP
    if request.client:
        return request.client.host
    
    # Last resort: return unknown
    return "unknown"


async def check_rate_limit(ip_address: str) -> Dict[str, Any]:
    """
    Check if the IP address has exceeded the rate limit.
    
    Args:
        ip_address: Client IP address
        
    Returns:
        Dictionary with rate limit status:
        {
            "allowed": bool,
            "remaining_requests": int,
            "reset_time": Optional[datetime],
            "total_requests": int
        }
    """
    async with _rate_limit_lock:
        current_time = time.time()
        
        # Get or initialize request timestamps for this IP
        timestamps = _rate_limit_store.get(ip_address, [])
        
        # Clean up expired timestamps (older than WINDOW_SECONDS)
        cutoff_time = current_time - WINDOW_SECONDS
        valid_timestamps = [ts for ts in timestamps if ts > cutoff_time]
        
        # Update store with cleaned timestamps
        if len(valid_timestamps) < len(timestamps):
            _rate_limit_store[ip_address] = valid_timestamps
            # Remove IP entry if no valid timestamps remain
            if not valid_timestamps:
                _rate_limit_store.pop(ip_address, None)
        
        # Check if limit exceeded
        total_requests = len(valid_timestamps)
        allowed = total_requests < MAX_REQUESTS
        remaining_requests = max(0, MAX_REQUESTS - total_requests)
        
        # Calculate reset time (earliest timestamp + window)
        reset_time = None
        if valid_timestamps:
            earliest_timestamp = min(valid_timestamps)
            reset_time = datetime.fromtimestamp(earliest_timestamp + WINDOW_SECONDS)
        
        # If allowed, add current timestamp
        if allowed:
            valid_timestamps.append(current_time)
            _rate_limit_store[ip_address] = valid_timestamps
        
        return {
            "allowed": allowed,
            "remaining_requests": remaining_requests,
            "reset_time": reset_time,
            "total_requests": total_requests
        }


async def periodic_cleanup():
    """
    Background task to periodically clean up expired rate limit entries.
    Runs every 5 minutes to prevent memory leaks.
    """
    while True:
        try:
            await asyncio.sleep(300)  # Run every 5 minutes
            await cleanup_expired_entries()
        except asyncio.CancelledError:
            logger.info("Rate limit cleanup task cancelled")
            break
        except Exception as e:
            logger.error(f"Error in rate limit cleanup task: {e}")


async def cleanup_expired_entries():
    """
    Clean up expired entries from rate limit store.
    """
    async with _rate_limit_lock:
        current_time = time.time()
        cutoff_time = current_time - WINDOW_SECONDS
        
        expired_ips = []
        for ip_address, timestamps in _rate_limit_store.items():
            valid_timestamps = [ts for ts in timestamps if ts > cutoff_time]
            if valid_timestamps:
                _rate_limit_store[ip_address] = valid_timestamps
            else:
                expired_ips.append(ip_address)
        
        # Remove IPs with no valid timestamps
        for ip_address in expired_ips:
            _rate_limit_store.pop(ip_address, None)
        
        if expired_ips:
            logger.debug(f"Cleaned up {len(expired_ips)} expired rate limit entries")


def rate_limit(func):
    """
    Decorator for rate limiting API endpoints.
    
    Usage:
        @rate_limit
        @router.post("/api/v1/intelligent-analysis")
        async def intelligent_analysis(request: Request, data: IntelligentAnalysisRequest):
            ...
    
    Raises:
        HTTPException(429): When rate limit is exceeded
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        # Find Request object in args or kwargs
        request = None
        for arg in args:
            if isinstance(arg, Request):
                request = arg
                break
        
        if not request:
            request = kwargs.get("request")
        
        if not request:
            logger.warning("Rate limit decorator used but Request object not found")
            # Continue without rate limiting if Request not found
            return await func(*args, **kwargs)
        
        # Get client IP
        ip_address = get_client_ip(request)
        
        # Check rate limit
        rate_limit_status = await check_rate_limit(ip_address)
        
        if not rate_limit_status["allowed"]:
            reset_time = rate_limit_status["reset_time"]
            reset_time_str = reset_time.isoformat() if reset_time else "N/A"
            
            logger.warning(
                f"Rate limit exceeded for IP {ip_address}: "
                f"{rate_limit_status['total_requests']}/{MAX_REQUESTS} requests "
                f"in {WINDOW_MINUTES} minutes"
            )
            
            raise HTTPException(
                status_code=429,
                detail={
                    "error": f"Rate limit exceeded. Maximum {MAX_REQUESTS} requests per {WINDOW_MINUTES} minutes. Please try again later.",
                    "remaining_requests": 0,
                    "reset_time": reset_time_str,
                    "max_requests": MAX_REQUESTS,
                    "window_minutes": WINDOW_MINUTES
                }
            )
        
        # Log if approaching limit (for monitoring)
        if rate_limit_status["remaining_requests"] <= 2:
            logger.info(
                f"IP {ip_address} approaching rate limit: "
                f"{rate_limit_status['remaining_requests']} requests remaining"
            )
        
        # Call the original function
        return await func(*args, **kwargs)
    
    return wrapper


def start_cleanup_task():
    """
    Start the background cleanup task.
    Should be called during application startup.
    """
    global _cleanup_task
    if _cleanup_task is None or _cleanup_task.done():
        _cleanup_task = asyncio.create_task(periodic_cleanup())
        logger.info("Rate limit cleanup task started")


def stop_cleanup_task():
    """
    Stop the background cleanup task.
    Should be called during application shutdown.
    """
    global _cleanup_task
    if _cleanup_task and not _cleanup_task.done():
        _cleanup_task.cancel()
        logger.info("Rate limit cleanup task stopped")

