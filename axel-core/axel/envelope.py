from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


def new_event_id() -> str:
    return f"evt_{uuid4().hex[:12]}"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class Envelope(BaseModel):
    event_id: str = Field(default_factory=new_event_id)
    received_at: str = Field(default_factory=now_iso)
    channel: str = "test"
    direction: str = "in"
    channel_user_id: str = "test_user"
    customer_id: Optional[str] = None
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    known_context: list[str] = Field(default_factory=list)
    business_id: str = "biz_default"
    intent: Optional[str] = None
    agent: Optional[str] = None
    supervision_level: int = 1
    model: Optional[str] = None
    model_reason: Optional[str] = None
    text: str = ""
    context_refs: list[str] = Field(default_factory=list)
    payload: dict[str, Any] = Field(default_factory=dict)
    result: Optional[str] = None
    reply_text: Optional[str] = None
    approval_status: str = "na"
    why: Optional[str] = None
    owner_notified: bool = False
    error: Optional[str] = None
