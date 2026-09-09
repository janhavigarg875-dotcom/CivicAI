"""
ComplaintService — persists confirmed complaints to SQLite and generates
simulated complaint IDs.

Complaint ID format: CIV-<SCOPE>-<YYYYMMDD>-<5-digit-random>
Example:            CIV-CAMPUS-20240115-48291

IMPORTANT: This is a simulation. No real authority is ever notified.
The transparency disclaimer is always included in responses.
"""
from __future__ import annotations

import logging
import random
import string
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from core.enums import ComplaintStatus, ScopeType
from models.complaint import Complaint
from schemas.complaint import ComplaintRequest, ComplaintResponse, ComplaintStatusResponse
from services.guardrail_service import guardrail_service

logger = logging.getLogger(__name__)

_DISCLAIMER = (
    "⚠️ This is a simulated complaint record. "
    "No real complaint has been submitted and no real authority has been notified. "
    "CivicAI is an AI assistant — complaints are logged for demonstration purposes only."
)

_SCOPE_ROUTING: dict[str, str] = {
    ScopeType.CAMPUS.value: "Campus Management / Maintenance",
    ScopeType.CITY.value:   "Municipal / Civic Authority",
}


def _generate_complaint_id(scope: str) -> str:
    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    suffix = "".join(random.choices(string.digits, k=5))
    return f"CIV-{scope}-{date_str}-{suffix}"


class ComplaintService:

    def register(self, req: ComplaintRequest, db: Session) -> ComplaintResponse:
        """
        Persist a confirmed complaint to SQLite and return a ComplaintResponse.
        The caller MUST have already verified req.confirmed == True before calling this.
        """
        if not req.confirmed:
            raise ValueError("ComplaintService.register() called without user confirmation.")

        complaint_id = _generate_complaint_id(req.scope.value)
        routed_to = _SCOPE_ROUTING.get(req.scope.value, "Campus Management / Maintenance")
        now = datetime.now(timezone.utc)

        # RAI Gate 3 — sanitize free-text fields before storage
        safe_description = guardrail_service.sanitize_complaint_text(req.description or "")
        safe_previous_action = guardrail_service.sanitize_complaint_text(req.previous_action or "")

        complaint = Complaint(
            id=complaint_id,
            category=req.category.value,
            scope=req.scope.value,
            issue_summary=req.issue_summary,
            location=req.location,
            duration=req.duration,
            description=safe_description or None,
            previous_action=safe_previous_action or None,
            status=ComplaintStatus.OPEN.value,
            routed_to=routed_to,
            created_at=now,
        )
        db.add(complaint)
        db.commit()
        db.refresh(complaint)

        logger.info("Complaint registered: %s → %s", complaint_id, routed_to)

        message = (
            f"✅ Your complaint has been logged with ID **{complaint_id}**.\n\n"
            f"It has been conceptually routed to: **{routed_to}**.\n\n"
            f"{_DISCLAIMER}"
        )

        return ComplaintResponse(
            id=complaint_id,
            category=req.category.value,
            scope=req.scope.value,
            routed_to=routed_to,
            status=ComplaintStatus.OPEN,
            created_at=now,
            message=message,
        )

    def get_status(self, complaint_id: str, db: Session) -> ComplaintStatusResponse | None:
        """Return the status of a complaint, or None if not found."""
        complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
        if complaint is None:
            return None
        return ComplaintStatusResponse(
            id=complaint.id,
            category=complaint.category,
            scope=complaint.scope,
            issue_summary=complaint.issue_summary,
            location=complaint.location,
            routed_to=complaint.routed_to,
            status=ComplaintStatus(complaint.status),
            created_at=complaint.created_at,
        )


# Module-level singleton
complaint_service = ComplaintService()
