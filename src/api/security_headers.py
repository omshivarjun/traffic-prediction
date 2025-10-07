"""
Security Headers Middleware for Traffic Analytics API

Implements comprehensive security headers to protect against common web vulnerabilities.
Headers included:
- Strict-Transport-Security (HSTS)
- Content-Security-Policy (CSP)
- X-Content-Type-Options
- X-Frame-Options
- X-XSS-Protection
- Permissions-Policy
- Referrer-Policy
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from typing import Callable
import logging

from .logging_config import api_logger


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add security headers to all HTTP responses.
    
    Security headers help protect against:
    - Cross-Site Scripting (XSS)
    - Clickjacking
    - MIME type sniffing
    - Man-in-the-middle attacks
    - Information leakage
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process the request and add security headers to the response.
        
        Args:
            request: The incoming HTTP request
            call_next: The next middleware or route handler
            
        Returns:
            Response with security headers added
        """
        response = await call_next(request)
        
        # Strict-Transport-Security (HSTS)
        # Forces HTTPS connections for 1 year, including subdomains
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        # Content-Security-Policy (CSP)
        # Restricts resource loading to prevent XSS attacks
        # Note: Adjust 'unsafe-inline' and 'unsafe-eval' based on frontend needs
        csp_directives = [
            "default-src 'self'",
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'",  # Allow inline scripts for FastAPI docs
            "style-src 'self' 'unsafe-inline'",  # Allow inline styles for FastAPI docs
            "img-src 'self' data: https:",
            "font-src 'self' data:",
            "connect-src 'self' ws: wss:",  # Allow WebSocket connections
            "frame-ancestors 'none'",
            "base-uri 'self'",
            "form-action 'self'"
        ]
        response.headers["Content-Security-Policy"] = "; ".join(csp_directives)
        
        # X-Content-Type-Options
        # Prevents MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"
        
        # X-Frame-Options
        # Prevents clickjacking by disallowing embedding in frames
        response.headers["X-Frame-Options"] = "DENY"
        
        # X-XSS-Protection
        # Legacy XSS protection (browsers mostly use CSP now)
        response.headers["X-XSS-Protection"] = "1; mode=block"
        
        # Permissions-Policy (formerly Feature-Policy)
        # Restricts access to browser features
        permissions_directives = [
            "geolocation=()",
            "microphone=()",
            "camera=()",
            "payment=()",
            "usb=()",
            "magnetometer=()",
            "accelerometer=()",
            "gyroscope=()"
        ]
        response.headers["Permissions-Policy"] = ", ".join(permissions_directives)
        
        # Referrer-Policy
        # Controls how much referrer information is sent
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # Remove server identification header for security
        if "Server" in response.headers:
            del response.headers["Server"]
        
        # Add custom security header for tracking
        response.headers["X-Security-Headers"] = "enabled"
        
        return response


class RateLimitHeaderMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add rate limit information to response headers.
    
    Provides visibility into rate limiting status for API clients.
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Add rate limit headers to the response.
        
        Args:
            request: The incoming HTTP request
            call_next: The next middleware or route handler
            
        Returns:
            Response with rate limit headers
        """
        response = await call_next(request)
        
        # Add rate limit headers if they don't already exist
        # These will be populated by slowapi
        if "X-RateLimit-Limit" not in response.headers:
            response.headers["X-RateLimit-Limit"] = "100"
        
        if "X-RateLimit-Remaining" not in response.headers:
            response.headers["X-RateLimit-Remaining"] = "100"
        
        if "X-RateLimit-Reset" not in response.headers:
            # Set reset time to 1 minute from now
            import time
            response.headers["X-RateLimit-Reset"] = str(int(time.time()) + 60)
        
        return response


def log_security_headers_enabled():
    """Log that security headers middleware has been enabled."""
    api_logger.info("Security headers middleware enabled")
    api_logger.info("Security features active: HSTS, CSP, X-Frame-Options, X-XSS-Protection, Permissions-Policy")
