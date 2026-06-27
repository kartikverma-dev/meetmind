"""Action Items router supporting interactive task lists, filters, and status toggles."""

import logging
from uuid import UUID
from typing import List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException

from config import get_settings
from routes.auth import get_current_user
from services.supabase_client import SupabaseNotConfiguredError, get_supabase
from routes.meetings import run_db_query, MOCK_MEETINGS

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/action-items", tags=["action-items"])

class ActionItemUpdate(BaseModel):
    status: str  # 'pending' or 'done'

class ActionItemResponse(BaseModel):
    id: str
    meeting_id: str
    meeting_title: Optional[str] = None
    task: str
    owner: Optional[str] = None
    deadline: Optional[str] = None
    status: str

@router.get("", response_model=List[ActionItemResponse])
async def get_action_items(
    meeting_id: Optional[str] = None,
    current_user = Depends(get_current_user)
):
    """Retrieve action items for the logged in user, optionally filtered by meeting_id."""
    settings = get_settings()
    resolved_user_id = str(current_user.id)

    # --- MOCK MODE ---
    if settings.mock_mode:
        results = []
        for m in MOCK_MEETINGS:
            if str(m.get("user_id")) != resolved_user_id:
                continue
            if meeting_id and str(m.get("id")) != str(meeting_id):
                continue
            
            mom = m.get("mom") or {}
            action_items = mom.get("action_items") or []
            
            for idx, item in enumerate(action_items):
                # Ensure the mock item has status, default to pending
                status = item.get("status", "pending")
                item_id = f"mock-ai-{m.get('id')}-{idx}"
                results.append(ActionItemResponse(
                    id=item_id,
                    meeting_id=str(m.get("id")),
                    meeting_title=m.get("title", "Untitled Meeting"),
                    task=item.get("task", ""),
                    owner=item.get("owner"),
                    deadline=item.get("deadline"),
                    status=status
                ))
        return results

    # --- SUPABASE MODE ---
    try:
        supabase = get_supabase()
    except SupabaseNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    try:
        query = supabase.table("action_items").select("*, meetings(title)").eq("user_id", resolved_user_id)
        if meeting_id:
            query = query.eq("meeting_id", str(meeting_id))
            
        result = await run_db_query(query.execute)
        
        mapped_items = []
        for row in result.data:
            meetings_data = row.get("meetings") or {}
            meeting_title = meetings_data.get("title", "Untitled Meeting")
            
            mapped_items.append(ActionItemResponse(
                id=str(row["id"]),
                meeting_id=str(row["meeting_id"]),
                meeting_title=meeting_title,
                task=row["task"],
                owner=row.get("owner"),
                deadline=row.get("deadline"),
                status=row["status"]
            ))
        return mapped_items
    except Exception as exc:
        logger.exception("Failed to query action items")
        raise HTTPException(status_code=500, detail=f"Database query failed: {exc}")


@router.patch("/{action_item_id}", response_model=ActionItemResponse)
async def update_action_item(
    action_item_id: str,
    body: ActionItemUpdate,
    current_user = Depends(get_current_user)
):
    """Toggle action item status between 'pending' and 'done'."""
    settings = get_settings()
    resolved_user_id = str(current_user.id)

    if body.status not in ["pending", "done"]:
        raise HTTPException(status_code=400, detail="Invalid status. Allowed: 'pending', 'done'")

    # --- MOCK MODE ---
    if settings.mock_mode:
        if not action_item_id.startswith("mock-ai-"):
            raise HTTPException(status_code=404, detail="Mock Action Item not found")
        
        parts = action_item_id.replace("mock-ai-", "").split("-")
        if len(parts) < 2:
            raise HTTPException(status_code=400, detail="Malformed mock ID")
        
        idx = int(parts[-1])
        meet_id = "-".join(parts[:-1])
        
        # Find meeting
        target_meeting = None
        for m in MOCK_MEETINGS:
            if str(m.get("id")) == meet_id and str(m.get("user_id")) == resolved_user_id:
                target_meeting = m
                break
                
        if not target_meeting:
            raise HTTPException(status_code=404, detail="Associated meeting not found")
            
        mom = target_meeting.get("mom") or {}
        action_items = mom.get("action_items") or []
        
        if idx >= len(action_items):
            raise HTTPException(status_code=404, detail="Mock Action Item out of range")
            
        action_items[idx]["status"] = body.status
        
        return ActionItemResponse(
            id=action_item_id,
            meeting_id=meet_id,
            meeting_title=target_meeting.get("title", "Untitled Meeting"),
            task=action_items[idx].get("task", ""),
            owner=action_items[idx].get("owner"),
            deadline=action_items[idx].get("deadline"),
            status=body.status
        )

    # --- SUPABASE MODE ---
    try:
        supabase = get_supabase()
    except SupabaseNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    try:
        # Check ownership
        check_result = await run_db_query(
            supabase.table("action_items")
            .select("user_id, meeting_id, task, owner, deadline")
            .eq("id", action_item_id)
            .maybe_single()
            .execute
        )
        
        row = check_result.data
        if not row:
            raise HTTPException(status_code=404, detail="Action item not found")
        if str(row["user_id"]) != resolved_user_id:
            raise HTTPException(status_code=403, detail="You do not have permission to modify this action item")
            
        # Update status
        update_result = await run_db_query(
            supabase.table("action_items")
            .update({"status": body.status})
            .eq("id", action_item_id)
            .execute
        )
        
        updated_row = update_result.data[0]
        
        # Fetch title for response
        meet_result = await run_db_query(
            supabase.table("meetings").select("title").eq("id", updated_row["meeting_id"]).maybe_single().execute
        )
        meet_title = "Untitled Meeting"
        if meet_result.data:
            meet_title = meet_result.data.get("title", "Untitled Meeting")
            
        return ActionItemResponse(
            id=str(updated_row["id"]),
            meeting_id=str(updated_row["meeting_id"]),
            meeting_title=meet_title,
            task=updated_row["task"],
            owner=updated_row.get("owner"),
            deadline=updated_row.get("deadline"),
            status=updated_row["status"]
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to update action item")
        raise HTTPException(status_code=500, detail=f"Database update failed: {exc}")
