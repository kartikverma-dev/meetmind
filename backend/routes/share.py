"""Public share routes for accessing shared meeting summaries and MOM read-only."""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from config import get_settings
from services.supabase_client import SupabaseNotConfiguredError, get_supabase
from routes.meetings import run_db_query, MOCK_MEETINGS
from models.schemas import MOM

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/share", tags=["share"])

class SharedMeetingResponse(BaseModel):
    title: str
    summary: Optional[str] = None
    mom: Optional[MOM] = None
    created_at: str
    status: str

@router.get("/{slug}", response_model=SharedMeetingResponse)
async def get_shared_meeting(slug: str):
    """Retrieve shared meeting minutes via public slug without authentication."""
    settings = get_settings()

    # --- MOCK MODE ---
    if settings.mock_mode:
        row = None
        for m in MOCK_MEETINGS:
            # Check if this mock meeting has is_public=True and matching slug
            if m.get("is_public") and m.get("public_slug") == slug:
                row = m
                break
        if not row:
            raise HTTPException(status_code=404, detail="Shared meeting report not found or made private")
            
        return SharedMeetingResponse(
            title=row.get("title", "Untitled Meeting"),
            summary=row.get("summary"),
            mom=row.get("mom"),
            created_at=row.get("created_at"),
            status=row.get("status", "done")
        )

    # --- SUPABASE MODE ---
    try:
        supabase = get_supabase()
    except SupabaseNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    try:
        result = await run_db_query(
            supabase.table("meetings")
            .select("title, summary, mom, created_at, status")
            .eq("public_slug", slug)
            .eq("is_public", True)
            .maybe_single()
            .execute
        )
        
        row = result.data
        if not row:
            raise HTTPException(status_code=404, detail="Shared meeting report not found or made private")
            
        return SharedMeetingResponse(
            title=row["title"],
            summary=row.get("summary"),
            mom=row.get("mom"),
            created_at=row["created_at"],
            status=row["status"]
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to query shared meeting")
        raise HTTPException(status_code=500, detail=f"Database query failed: {exc}")
