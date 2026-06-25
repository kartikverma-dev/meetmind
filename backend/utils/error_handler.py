"""Global error handler middleware to catch all unhandled exceptions and log them safely."""

import uuid
import logging
import asyncio
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from services.supabase_client import get_supabase
from utils.logger import request_id_var, user_id_var

logger = logging.getLogger(__name__)

async def global_exception_handler(request: Request, exc: Exception):
    """
    Global exception handler to intercept exceptions, log them to Supabase in a non-blocking 
    background thread, and return safe responses with a Request ID.
    """
    request_id = request_id_var.get()
    if request_id == "-":
        request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
        request_id_var.set(request_id)
        
    user_id = user_id_var.get()
    if user_id == "-":
        user_id = None
        
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    detail = f"An internal server error occurred. Please contact support with Request ID: {request_id}"

    if isinstance(exc, HTTPException):
        status_code = exc.status_code
        detail = exc.detail
    else:
        logger.exception("Unhandled server error [RequestID: %s]: %s", request_id, exc)

    # Log to Supabase error_logs table if not mock mode
    try:
        from config import get_settings
        settings = get_settings()
        if not settings.mock_mode:
            supabase = get_supabase()
            ip_addr = request.client.host if request.client else None
            
            def do_insert():
                try:
                    # Sanitize message to prevent any script tag injection in db
                    sanitized_msg = str(exc)[:2000]
                    supabase.table("error_logs").insert({
                        "endpoint": f"{request.method} {request.url.path}",
                        "error_type": exc.__class__.__name__,
                        "message": sanitized_msg,
                        "user_id": user_id,
                        "ip_address": ip_addr,
                        "request_id": request_id,
                    }).execute()
                except Exception as log_inner_exc:
                    logger.error("Supabase insert thread failed: %s", log_inner_exc)

            asyncio.create_task(asyncio.to_thread(do_insert))
    except Exception as db_exc:
        logger.error("Failed to schedule exception logging to Supabase error_logs: %s", db_exc)

    return JSONResponse(
        status_code=status_code,
        content={
            "detail": detail,
            "request_id": request_id
        }
    )
