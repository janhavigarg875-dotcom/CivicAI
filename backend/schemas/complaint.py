from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from core.enums import CategoryType, ComplaintStatus, ScopeType


class ComplaintRequest(BaseModel):
    session_id: str
    category: CategoryType
    scope: ScopeType
    issue_summary: str = Field(..., min_length=3, max_length=255)
    location: str = Field(..., min_length=2, max_length=500)
    duration: Optional[str] = Field(default=None, max_length=100)
    description: Optional[str] = Field(default=None, max_length=2000)
    previous_action: Optional[str] = Field(default=None, max_length=1000)
    confirmed: bool = Field(..., description="Must be True — user has explicitly confirmed complaint submission.")


class ComplaintResponse(BaseModel):
    id: str
    category: str
    scope: str
    routed_to: str
    status: ComplaintStatus
    created_at: datetime
    message: str  # includes transparency disclaimer


class ComplaintStatusResponse(BaseModel):
    id: str
    category: str
    scope: str
    issue_summary: str
    location: str
    routed_to: str
    status: ComplaintStatus
    created_at: datetime
    disclaimer: str = (
        "This is a simulated complaint record. "
        "No real authority has been notified and no real action has been taken."
    )
