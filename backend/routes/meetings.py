"""Meeting upload and retrieval routes."""

import logging
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from config import get_settings
from services.supabase_client import SupabaseNotConfiguredError
from models.schemas import (
    MeetingResponse,
    MeetingStatus,
    MeetingUploadResponse,
    MOM,
)
from services.ai_processor import process_transcript
from services.supabase_client import get_supabase
from services.transcriber import transcribe_audio

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/meetings", tags=["meetings"])

# Allowed audio/video extensions for upload
ALLOWED_EXTENSIONS = {
    ".mp3", ".mp4", ".wav", ".m4a", ".webm", ".ogg", ".flac", ".mpeg", ".mpga",
}


def _validate_extension(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )
    return ext


def _resolve_user_id(user_id: str | None) -> str:
    """Resolve user_id from form field or TEST_USER_ID env (Phase 1 only)."""
    settings = get_settings()
    resolved = user_id or settings.test_user_id
    if not resolved:
        raise HTTPException(
            status_code=400,
            detail="user_id is required (or set TEST_USER_ID in .env for local testing)",
        )
    return resolved


@router.post("/upload", response_model=MeetingUploadResponse)
async def upload_meeting(
    file: UploadFile = File(...),
    title: str = Form(default="Untitled Meeting"),
    user_id: str | None = Form(default=None),
):
    """
    Upload an audio/video file, transcribe with Whisper, process with Claude,
    and persist the meeting to Supabase.

    Phase 1: pass user_id as form field or set TEST_USER_ID in .env.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    ext = _validate_extension(file.filename)
    resolved_user_id = _resolve_user_id(user_id)
    meeting_id = str(uuid.uuid4())
    try:
        supabase = get_supabase()
    except SupabaseNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    # Create meeting row with 'processing' status before heavy work
    now = datetime.now(timezone.utc).isoformat()
    supabase.table("meetings").insert(
        {
            "id": meeting_id,
            "user_id": resolved_user_id,
            "title": title,
            "transcript": None,
            "mom": None,
            "summary": None,
            "created_at": now,
            "status": MeetingStatus.PROCESSING.value,
        }
    ).execute()

    tmp_path: str | None = None
    try:
        # Save upload to a temp file for Whisper
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        transcript = await transcribe_audio(tmp_path)
        mom, summary = await process_transcript(transcript)

        supabase.table("meetings").update(
            {
                "transcript": transcript,
                "mom": mom.model_dump(),
                "summary": summary,
                "status": MeetingStatus.DONE.value,
            }
        ).eq("id", meeting_id).execute()

        return MeetingUploadResponse(
            id=UUID(meeting_id),
            status=MeetingStatus.DONE,
            message="Meeting processed successfully",
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Meeting processing failed for %s", meeting_id)
        supabase.table("meetings").update(
            {"status": MeetingStatus.FAILED.value}
        ).eq("id", meeting_id).execute()
        raise HTTPException(
            status_code=500,
            detail=f"Processing failed: {exc}",
        ) from exc
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


@router.get("/{meeting_id}", response_model=MeetingResponse)
async def get_meeting(meeting_id: UUID):
    """Return full meeting data by ID."""
    try:
        supabase = get_supabase()
    except SupabaseNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    result = (
        supabase.table("meetings")
        .select("*")
        .eq("id", str(meeting_id))
        .maybe_single()
        .execute()
    )

    row = result.data
    if not row:
        raise HTTPException(status_code=404, detail="Meeting not found")

    mom_data = row.get("mom")
    mom = MOM.model_validate(mom_data) if mom_data else None

    return MeetingResponse(
        id=UUID(row["id"]),
        user_id=UUID(row["user_id"]),
        title=row["title"],
        transcript=row.get("transcript"),
        mom=mom,
        summary=row.get("summary"),
        created_at=row["created_at"],
        status=MeetingStatus(row["status"]),
    )
