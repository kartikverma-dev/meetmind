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


import re
from pydantic import BaseModel, Field, field_validator

class UserCredentials(BaseModel):
    email: str
    password: str
    referral_code: Optional[str] = None

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, v: str) -> str:
        v = v.strip().lower()
        email_regex = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
        if not re.match(email_regex, v):
            raise ValueError("Invalid email format")
        return v

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not any(char.isupper() for char in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(char.islower() for char in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(char.isdigit() for char in v):
            raise ValueError("Password must contain at least one number")
        if not any(char in "!@#$%^&*(),.?\":{}|<>" for char in v):
            raise ValueError("Password must contain at least one special character")
        return v

class QuestionRequest(BaseModel):
    question: str = Field(..., max_length=500)


class UserResponse(BaseModel):
    id: UUID
    email: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class ProfileResponse(BaseModel):
    id: UUID
    email: str
    is_pro: bool
    pro_until: Optional[datetime] = None
    meetings_used: int
    razorpay_subscription_id: Optional[str] = None
    referred_by: Optional[str] = None
    referral_code: Optional[str] = None


