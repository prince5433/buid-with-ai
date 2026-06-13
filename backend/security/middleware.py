"""Security middleware: rate limiting, CORS, headers, input sanitization."""

import time
import re
from collections import defaultdict
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from config import settings


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Token bucket rate limiter per IP address."""

    def __init__(self, app):
        super().__init__(app)
        self._requests: dict[str, list[float]] = defaultdict(list)

    def _get_limit(self, path: str) -> int:
        """Get rate limit based on endpoint."""
        if "/upload" in path:
            return settings.rate_limit_uploads
        elif "/chat" in path:
            return settings.rate_limit_chat
        return 120  # Default: 120 req/min for other endpoints

    def _clean_old_requests(self, ip: str, window: float = 60.0):
        """Remove requests older than the window."""
        now = time.time()
        self._requests[ip] = [
            t for t in self._requests[ip] if now - t < window
        ]

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        path = request.url.path

        # Skip rate limiting for health checks and static files
        if path in ("/health", "/docs", "/openapi.json"):
            return await call_next(request)

        self._clean_old_requests(client_ip)
        limit = self._get_limit(path)

        if len(self._requests[client_ip]) >= limit:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded. Please try again later.",
                    "retry_after_seconds": 60,
                },
                headers={"Retry-After": "60"},
            )

        self._requests[client_ip].append(time.time())
        response = await call_next(request)
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        response.headers["Pragma"] = "no-cache"

        # Remove server header to prevent info leakage
        if "server" in response.headers:
            del response.headers["server"]

        return response


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Enforce maximum request body size."""

    MAX_BODY_SIZE = settings.max_file_size_mb * 1024 * 1024 * 4  # Allow batch uploads

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")

        if content_length and int(content_length) > self.MAX_BODY_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"Request body too large. Maximum allowed: {self.MAX_BODY_SIZE // (1024*1024)}MB",
            )

        return await call_next(request)


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to prevent path traversal and injection attacks.
    
    - Removes directory separators
    - Removes null bytes  
    - Strips leading dots
    - Limits length
    - Only allows safe characters
    """
    if not filename:
        return "unnamed_file"

    # Remove null bytes
    filename = filename.replace("\x00", "")

    # Get basename only (prevent path traversal)
    filename = filename.replace("\\", "/").split("/")[-1]

    # Remove leading dots (prevent hidden files)
    filename = filename.lstrip(".")

    # Only allow safe characters
    name, ext = (filename.rsplit(".", 1) + [""])[:2]
    name = re.sub(r'[^\w\s\-]', '', name).strip()
    ext = re.sub(r'[^\w]', '', ext).strip().lower()

    if not name:
        name = "unnamed_file"

    # Limit length
    name = name[:100]
    ext = ext[:10]

    return f"{name}.{ext}" if ext else name


def sanitize_chat_input(text: str) -> str:
    """Sanitize user chat input to prevent prompt injection basics."""
    if not text:
        return ""

    # Limit length
    text = text[:5000]

    # Remove null bytes
    text = text.replace("\x00", "")

    return text.strip()
