from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, field_validator


# ──────────────────────────────────────────────
# User Schemas
# ──────────────────────────────────────────────
class UserRegister(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_]+$")
    email: EmailStr
    password: str = Field(..., min_length=6)
    display_name: str = Field(..., min_length=1, max_length=100)


class UserLogin(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    id: int
    username: str
    email: str
    display_name: str
    avatar_color: str
    bio: Optional[str]
    is_online: bool
    last_seen: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    display_name: Optional[str] = Field(None, min_length=1, max_length=100)
    bio: Optional[str] = Field(None, max_length=300)
    avatar_color: Optional[str] = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")


# ──────────────────────────────────────────────
# Auth Schemas
# ──────────────────────────────────────────────
class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ──────────────────────────────────────────────
# Message Schemas
# ──────────────────────────────────────────────
class MessageCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=4000)
    reply_to_id: Optional[int] = None

    @field_validator("content")
    @classmethod
    def content_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Message cannot be empty or whitespace")
        return v.strip()


class MessageOut(BaseModel):
    id: int
    room_id: int
    sender_id: int
    sender_username: str
    sender_display_name: str
    sender_avatar_color: str
    content: str
    status: str
    reply_to_id: Optional[int]
    is_deleted: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ──────────────────────────────────────────────
# Room Schemas
# ──────────────────────────────────────────────
class RoomCreate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None, max_length=300)
    member_ids: list[int] = Field(default_factory=list)


class DirectRoomCreate(BaseModel):
    target_user_id: int


class RoomOut(BaseModel):
    id: int
    name: Optional[str]
    room_type: str
    description: Optional[str]
    created_by: int
    created_at: datetime
    member_count: int = 0
    last_message: Optional[MessageOut] = None
    unread_count: int = 0

    model_config = {"from_attributes": True}


class RoomMemberOut(BaseModel):
    user_id: int
    username: str
    display_name: str
    avatar_color: str
    is_online: bool
    is_admin: bool
    joined_at: datetime

    model_config = {"from_attributes": True}


# ──────────────────────────────────────────────
# WebSocket Event Schemas
# ──────────────────────────────────────────────
class WSEvent(BaseModel):
    type: str
    payload: dict


class PaginatedMessages(BaseModel):
    messages: list[MessageOut]
    total: int
    page: int
    page_size: int
    has_more: bool
