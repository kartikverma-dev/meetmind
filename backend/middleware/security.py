"""Security, Logging, and Intrusion Detection Middlewares for FastAPI."""

import os
import time
import uuid
import logging
import asyncio
from fastapi import Request, status
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware
from services.supabase_client import get_supabase
from utils.logger import request_id_var, user_id_var
from utils.sanitize import detect_injection_attempt

logger = logging.getLogger(__name__)

def log_suspicious_activity(event_type: str, ip_address: str, user_id: str, details: dict):
    """Log suspicious activities to the security_logs table in Supabase."""
    try:
        from config import get_settings
        if not get_settings().mock_mode:
            supabase = get_supabase()
            def do_insert():
                try:
                    supabase.table("security_logs").insert({
                        "event_type": event_type,
                        "ip_address": ip_address,
                        "user_id": user_id,
                        "details": details
                    }).execute()
                except Exception as inner_exc:
                    logger.error("Failed to write to security_logs table: %s", inner_exc)
            asyncio.create_task(asyncio.to_thread(do_insert))
    except Exception as exc:
        logger.error("Failed to schedule security activity log: %s", exc)

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware to inject standard protective security headers on all HTTP responses."""
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # Inject standard security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        # Safe Content Security Policy (allows Swagger UI and basic frontend connections)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' data: https://fonts.gstatic.com; "
            "img-src 'self' data:; "
            "connect-src 'self' ws: wss: https://*.supabase.co https://api.github.com;"
        )
        return response

class RequestSizeMiddleware(BaseHTTPMiddleware):
    """Middleware to reject request bodies exceeding the 600MB payload limit."""
    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                size = int(content_length)
                if size > 600 * 1024 * 1024:
                    return JSONResponse(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        content={"detail": "Payload too large. Request body exceeds 600MB limit."}
                    )
            except ValueError:
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={"detail": "Invalid Content-Length header format."}
                )
        return await call_next(request)

class HTTPSRedirectMiddleware(BaseHTTPMiddleware):
    """Middleware to redirect all non-secure HTTP requests to HTTPS in production environments."""
    async def dispatch(self, request: Request, call_next):
        env = os.getenv("ENV", "development").lower()
        if request.url.scheme == "http" and env == "production":
            secure_url = str(request.url).replace("http://", "https://", 1)
            return RedirectResponse(url=secure_url, status_code=status.HTTP_301_MOVED_PERMANENTLY)
        return await call_next(request)

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to safely log request metadata and execution times."""
    async def dispatch(self, request: Request, call_next):
        # Generate or read request ID
        req_id = request.headers.get("x-request-id", str(uuid.uuid4()))
        request_id_var.set(req_id)
        
        # User ID context (will be updated if route auth succeeds)
        user_id_var.set("-")
        
        start_time = time.time()
        ip_address = request.client.host if request.client else "-"
        
        # Pre-process request
        response = await call_next(request)
        
        # Post-process logging
        duration = time.time() - start_time
        user_id = user_id_var.get()
        
        # Exclude health-check polling from noisy logs
        if request.url.path not in ["/health", "/"]:
            logger.info(
                "Request processed: method=%s path=%s status=%d duration=%.4fs ip=%s user_id=%s",
                request.method, request.url.path, response.status_code, duration, ip_address, user_id
            )
            
        # Append request ID header to response
        response.headers["X-Request-ID"] = req_id
        return response

class SuspiciousActivityMiddleware(BaseHTTPMiddleware):
    """Middleware to scan incoming parameters and bodies for common injection patterns."""
    async def dispatch(self, request: Request, call_next):
        # Exclude scan for binary files or large uploads
        if request.url.path == "/meetings/upload":
            return await call_next(request)
            
        ip_address = request.client.host if request.client else "unknown"
        user_id = user_id_var.get()
        
        # 1. Scan query parameters
        for key, value in request.query_params.items():
            if detect_injection_attempt(value):
                log_suspicious_activity(
                    "injection_attempt", ip_address, user_id if user_id != "-" else None,
                    {"location": "query_params", "key": key, "value": value[:200]}
                )
                return JSONResponse(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    content={"detail": "Request rejected due to potential security injection risk."}
                )
                
        # 2. Scan JSON body (if present)
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            # Read body
            body = await request.body()
            # Restore body stream so FastAPI route can read it later
            async def receive():
                return {"type": "http.request", "body": body, "more_body": False}
            request._receive = receive
            
            try:
                body_str = body.decode("utf-8")
                if detect_injection_attempt(body_str):
                    log_suspicious_activity(
                        "injection_attempt", ip_address, user_id if user_id != "-" else None,
                        {"location": "body", "snippet": body_str[:500]}
                    )
                    return JSONResponse(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        content={"detail": "Request rejected due to potential security injection risk."}
                    )
            except Exception:
                pass
                
        return await call_next(request)


class CSRFMiddleware(BaseHTTPMiddleware):
    """Middleware to validate double-submit cookie CSRF tokens on state-changing methods."""
    async def dispatch(self, request: Request, call_next):
        if request.method in ["POST", "PUT", "DELETE"]:
            path = request.url.path
            # Normalize path (remove version prefix if any)
            norm_path = path.replace("/api/v1", "")
            # Exclude login, signup, cron, and logout from CSRF check because they handle cookie establishment
            if norm_path not in ["/auth/login", "/auth/signup", "/cron/reset-monthly", "/auth/logout"]:
                csrf_cookie = request.cookies.get("csrf_token")
                csrf_header = request.headers.get("x-csrf-token")
                if not csrf_cookie or csrf_cookie != csrf_header:
                    return JSONResponse(
                        status_code=status.HTTP_403_FORBIDDEN,
                        content={"detail": "CSRF validation failed."}
                    )
        return await call_next(request)
