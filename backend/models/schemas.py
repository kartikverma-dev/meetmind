"""Pydantic models for request/response validation."""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class MeetingStatus(str, Enum):
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


class ActionItem(BaseModel):
    task: str
    owner: str
    deadline: Optional[str] = None


class MOM(BaseModel):
    attendees: list[str] = Field(default_factory=list)
    date: Optional[str] = None
    agenda: list[str] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)
    action_items: list[ActionItem] = Field(default_factory=list)


class MeetingUploadResponse(BaseModel):
    id: UUID
    status: MeetingStatus
    message: str


class MeetingResponse(BaseModel):
    id: UUID
    user_id: UUID
    title: str
    transcript: Optional[str] = None
    mom: Optional[MOM] = None
    summary: Optional[str] = None
    created_at: datetime
    status: MeetingStatus
