from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from core.enums import CategoryType, IntentType, ScopeType


class ChatRequest(BaseModel):
    session_id: str = Field(..., description="Client-generated UUID identifying the conversation session.")
    message: str = Field(..., min_length=1, max_length=4000, description="User's natural-language message.")


class ClassificationResult(BaseModel):
    intent: IntentType
    category: Optional[CategoryType] = None
    scope: Optional[ScopeType] = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class ChatResponse(BaseModel):
    session_id: str
    message: str
    classification: Optional[ClassificationResult] = None
    requires_confirmation: bool = False
    complaint_draft: Optional[dict] = None
    phase: Optional[str] = None
