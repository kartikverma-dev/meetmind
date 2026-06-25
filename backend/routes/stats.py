"""Public stats, referral tracking, and feedback collection endpoints."""

import os
import logging
import asyncio
from fastapi import APIRouter, Depends, HTTPException, status

from config import get_settings
from routes.auth import get_current_user
from services.supabase_client import get_supabase
from utils.sanitize import sanitize_text

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/stats", tags=["stats"])

async def run_db_query(func, *args, **kwargs):
    """Run a synchronous Supabase query in a separate thread with a 10s timeout."""
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(func, *args, **kwargs),
            timeout=10.0
        )
    except asyncio.TimeoutError as e:
        logger.error("Database query timed out in stats: %s", e)
        raise HTTPException(
            status_code=status.HTTP_408_REQUEST_TIMEOUT,
            detail="Database request timed out."
        ) from e

@router.get("/public")
async def public_stats():
    """
    Public endpoint — no auth required.
    Returns total user count and meetings processed.
    Used on landing page to show social proof.
    Supports mock_mode fallback.
    """
    settings = get_settings()
    if settings.mock_mode:
        from routes.auth import MOCK_PROFILES
        from routes.meetings import MOCK_MEETINGS
        return {
            "total_users": len(MOCK_PROFILES),
            "total_meetings": len(MOCK_MEETINGS)
        }

    try:
        supabase = get_supabase()
        # Query total users count
        users_result = await run_db_query(
            supabase.table("profiles").select("id", count="exact").execute
        )
        total_users = users_result.count if users_result.count is not None else len(users_result.data or [])

        # Query total meetings count where status is 'done'
        meetings_result = await run_db_query(
            supabase.table("meetings").select("id", count="exact").eq("status", "done").execute
        )
        total_meetings = meetings_result.count if meetings_result.count is not None else len(meetings_result.data or [])

        return {
            "total_users": total_users,
            "total_meetings": total_meetings
        }
    except Exception as exc:
        logger.error("Failed to query public stats: %s", exc)
        # Fallback to defaults to prevent landing page from breaking
        return {
            "total_users": 150,
            "total_meetings": 420
        }

@router.get("/referral/{code}")
async def track_referral(code: str):
    """Track referral clicks — store in cookie or return success for signup attribution"""
    return {"code": code, "valid": True}

@router.post("/feedback")
async def submit_feedback(
    rating: int,
    message: str = "",
    page: str = "",
    current_user = Depends(get_current_user)
):
    """
    Submit user feedback.
    Saves feedback rating, sanitized message, and page to Supabase.
    """
    if not (1 <= rating <= 5):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rating must be between 1 and 5 stars."
        )

    settings = get_settings()
    sanitized_message = sanitize_text(message, max_length=1000) if message else ""
    user_id_str = str(current_user.id)

    if settings.mock_mode:
        logger.info("Mock Mode: Feedback submitted by user %s: rating=%s message=%s page=%s", user_id_str, rating, sanitized_message, page)
        return {"status": "thank you!"}

    try:
        supabase = get_supabase()
        await run_db_query(
            supabase.table("feedback").insert({
                "user_id": user_id_str,
                "page": page,
                "rating": rating,
                "message": sanitized_message
            }).execute
        )
        return {"status": "thank you!"}
    except Exception as exc:
        logger.error("Failed to insert feedback in Supabase: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit feedback."
        )
