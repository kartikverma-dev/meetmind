"""Q&A routes for querying meeting transcripts with rate limiting, sanitization, and database query timeouts."""

import logging
import asyncio
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from middleware.rate_limit import limiter, LIMIT_QA
from routes.auth import get_current_user, check_limits
from services.supabase_client import get_supabase, SupabaseNotConfiguredError
from services.qa_service import answer_question
from config import get_settings
from utils.sanitize import sanitize_text, detect_injection_attempt

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/qa", tags=["qa"])

async def run_db_query(func, *args, **kwargs):
    """Run a synchronous Supabase query in a separate thread with a 10s timeout."""
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(func, *args, **kwargs),
            timeout=10.0
        )
    except asyncio.TimeoutError as e:
        logger.error("Supabase database query timed out in QA: %s", e)
        raise HTTPException(
            status_code=status.HTTP_408_REQUEST_TIMEOUT,
            detail="Database request timed out."
        ) from e

@router.get("/{meeting_id}")
@limiter.limit(LIMIT_QA)
async def ask_question_on_meeting(
    request: Request,
    meeting_id: UUID,
    q: str = Query(..., description="The question about the meeting transcript"),
    current_user = Depends(get_current_user),
    profile = Depends(check_limits),
):
    """
    Ask a question about a meeting transcript.
    Verifies that the caller owns the meeting.
    Supports mock_mode fallback.
    """
    # Enforce Q&A question length-limit (max 500 chars)
    if len(q) > 500:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Question is too long. Maximum allowed is 500 characters."
        )

    # Detect injection attempts
    if detect_injection_attempt(q):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Request rejected due to potential security injection risk."
        )

    # Sanitize query parameter input
    q = sanitize_text(q, max_length=500)

    settings = get_settings()
    if settings.mock_mode:
        from routes.meetings import MOCK_MEETINGS
        row = None
        for m in MOCK_MEETINGS:
            if str(m["id"]) == str(meeting_id):
                row = m
                break
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Meeting not found",
            )

        if str(row["user_id"]) != str(current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this meeting",
            )

        # Generate simple rule-based mock chatbot answer
        q_lower = q.lower()
        if "alice" in q_lower:
            answer = "According to the notes, Alice is responsible for shipping the Q3 summary module by next week (target: June 30)."
        elif "bob" in q_lower:
            answer = "Bob's primary action item is to write the related unit tests for the summary module, with a deadline set for June 29."
        elif "decision" in q_lower or "decided" in q_lower:
            answer = "The main decisions reached were to ship the summary module by next week and target Tuesday morning for the official launch."
        elif "agenda" in q_lower:
            answer = "The agenda focused on aligning Q3 execution timelines and finalizing the ship date for the summary module."
        else:
            answer = f"Based on the meeting transcript, the team discussed Q3 planning and shipping the summary module. Your question regarding '{q}' is addressed by the timelines set for Alice (June 30) and Bob (June 29)."

        return {"answer": answer}

    try:
        supabase = get_supabase()
    except SupabaseNotConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    # Fetch meeting transcript and owner ID with timeout wrapper
    result = await run_db_query(
        supabase.table("meetings")
        .select("user_id", "transcript")
        .eq("id", str(meeting_id))
        .maybe_single()
        .execute
    )

    row = result.data
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meeting not found",
        )

    # Check ownership
    if str(row["user_id"]) != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this meeting",
        )

    transcript = row.get("transcript")
    if not transcript:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Meeting transcript is empty or still processing",
        )

    # Generate answer using Gemini Q&A Service
    try:
        answer = await answer_question(transcript, q)
        return {"answer": answer}
    except Exception as exc:
        logger.exception("Q&A answering failed for meeting %s", meeting_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Answering failed. Please try again later.",
        ) from exc
