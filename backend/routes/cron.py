"""Cron reset endpoints with rate limiting, DB timeouts, and secret validation."""

import os
import logging
import asyncio
from fastapi import APIRouter, HTTPException, Header, Request, status

from middleware.rate_limit import limiter, LIMIT_CRON
from config import get_settings
from routes.auth import MOCK_PROFILES
from services.supabase_client import get_supabase

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/cron", tags=["cron"])

async def run_db_query(func, *args, **kwargs):
    """Run synchronous Supabase query in a separate thread with a 10s timeout."""
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(func, *args, **kwargs),
            timeout=10.0
        )
    except asyncio.TimeoutError as e:
        logger.error("Supabase database query timed out in Cron: %s", e)
        raise HTTPException(
            status_code=status.HTTP_408_REQUEST_TIMEOUT,
            detail="Database request timed out."
        ) from e

@router.post("/reset-monthly")
@limiter.limit(LIMIT_CRON)
async def reset_monthly(request: Request, x_cron_secret: str = Header(None, alias="X-Cron-Secret")):
    """
    Set meetings_used = 0 for all free users.
    Called by Render cron on the 1st of every month.
    """
    settings = get_settings()
    expected_secret = settings.cron_secret or os.getenv("CRON_SECRET", "")

    # Enforce minimum 32 character hex / strong string for the cron secret
    if not expected_secret or len(expected_secret) < 32:
        logger.error("Cron secret is weak or missing in environment variables.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal configuration error: cron secret requirements not met."
        )

    if x_cron_secret != expected_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: Invalid cron secret header",
        )

    if settings.mock_mode:
        logger.info("Mock Mode: Resetting monthly meeting counts in MOCK_PROFILES")
        for user_id, profile in MOCK_PROFILES.items():
            if not profile.get("is_pro", False):
                profile["meetings_used"] = 0
        return {"status": "success", "message": "Mock profiles reset successfully"}

    try:
        supabase = get_supabase()
        logger.info("Resetting meetings_used to 0 for all free users in Supabase")
        
        # Execute Supabase update with 10s timeout
        await run_db_query(
            supabase.table("profiles").update({"meetings_used": 0}).eq("is_pro", False).execute
        )
        return {"status": "success", "message": "Monthly meeting usage reset successfully"}
    except Exception as exc:
        logger.exception("Failed to reset monthly meeting usage")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Reset monthly usage failed."
        )
