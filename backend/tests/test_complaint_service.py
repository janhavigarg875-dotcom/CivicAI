"""
Tests for ComplaintService — ID format, routing, persistence, and status retrieval.
Uses an in-memory SQLite database (from conftest.py).
"""
import re
import pytest
from datetime import datetime, timezone

from core.enums import CategoryType, ComplaintStatus, ScopeType
from schemas.complaint import ComplaintRequest
from services.complaint_service import ComplaintService


@pytest.fixture
def svc():
    return ComplaintService()


def _make_request(**overrides) -> ComplaintRequest:
    defaults = dict(
        session_id="test-session",
        category=CategoryType.WATER,
        scope=ScopeType.CAMPUS,
        issue_summary="Water pipe leaking in Block C bathroom",
        location="Block C, Room 204, 2nd floor",
        duration="3 days",
        description="Constant drip from under-sink pipe",
        previous_action="Reported to floor supervisor",
        confirmed=True,
    )
    defaults.update(overrides)
    return ComplaintRequest(**defaults)


class TestComplaintIDFormat:
    def test_campus_id_format(self, svc, db_session):
        req = _make_request(scope=ScopeType.CAMPUS)
        resp = svc.register(req, db_session)
        assert re.match(r"^CIV-CAMPUS-\d{8}-\d{5}$", resp.id), f"Bad ID: {resp.id}"

    def test_city_id_format(self, svc, db_session):
        req = _make_request(scope=ScopeType.CITY)
        resp = svc.register(req, db_session)
        assert re.match(r"^CIV-CITY-\d{8}-\d{5}$", resp.id), f"Bad ID: {resp.id}"

    def test_two_complaints_have_different_ids(self, svc, db_session):
        r1 = svc.register(_make_request(), db_session)
        r2 = svc.register(_make_request(), db_session)
        assert r1.id != r2.id


class TestComplaintRouting:
    def test_campus_routed_to_campus_management(self, svc, db_session):
        resp = svc.register(_make_request(scope=ScopeType.CAMPUS), db_session)
        assert "Campus Management" in resp.routed_to or "Maintenance" in resp.routed_to

    def test_city_routed_to_municipal_authority(self, svc, db_session):
        resp = svc.register(_make_request(scope=ScopeType.CITY), db_session)
        assert "Municipal" in resp.routed_to or "Civic" in resp.routed_to


class TestComplaintPersistence:
    def test_complaint_status_defaults_to_open(self, svc, db_session):
        resp = svc.register(_make_request(), db_session)
        assert resp.status == ComplaintStatus.OPEN

    def test_complaint_response_has_disclaimer(self, svc, db_session):
        resp = svc.register(_make_request(), db_session)
        assert "simulated" in resp.message.lower()
        assert "no real" in resp.message.lower() or "no real authority" in resp.message.lower()

    def test_confirmed_false_raises(self, svc, db_session):
        req = _make_request(confirmed=False)
        with pytest.raises((ValueError, Exception)):
            svc.register(req, db_session)

    def test_created_at_is_recent(self, svc, db_session):
        before = datetime.now(timezone.utc).replace(tzinfo=None)
        resp = svc.register(_make_request(), db_session)
        after = datetime.now(timezone.utc).replace(tzinfo=None)
        # created_at is stored as naive UTC datetime
        created = resp.created_at.replace(tzinfo=None) if resp.created_at.tzinfo else resp.created_at
        assert before <= created <= after


class TestComplaintStatusRetrieval:
    def test_get_existing_complaint(self, svc, db_session):
        reg = svc.register(_make_request(), db_session)
        status = svc.get_status(reg.id, db_session)
        assert status is not None
        assert status.id == reg.id
        assert status.status == ComplaintStatus.OPEN
        assert "simulated" in status.disclaimer.lower()

    def test_get_nonexistent_complaint_returns_none(self, svc, db_session):
        result = svc.get_status("CIV-CAMPUS-99999999-00000", db_session)
        assert result is None

    def test_complaint_fields_persisted_correctly(self, svc, db_session):
        req = _make_request(location="Science Block, Lab 3", duration="1 week")
        reg = svc.register(req, db_session)
        status = svc.get_status(reg.id, db_session)
        assert status.location == "Science Block, Lab 3"


class TestComplaintPIISanitization:
    """Verify that PII sanitization runs via the guardrail gate."""

    def test_email_in_description_is_sanitized(self, svc, db_session):
        req = _make_request(description="Contact me at john@example.com for updates")
        svc.register(req, db_session)
        # Verify the stored record does not contain the raw email
        from models.complaint import Complaint
        record = db_session.query(Complaint).order_by(Complaint.created_at.desc()).first()
        assert "john@example.com" not in (record.description or "")
        assert "[EMAIL REMOVED]" in (record.description or "")

    def test_phone_in_previous_action_is_sanitized(self, svc, db_session):
        req = _make_request(previous_action="Called 9876543210 but no response")
        svc.register(req, db_session)
        from models.complaint import Complaint
        record = db_session.query(Complaint).order_by(Complaint.created_at.desc()).first()
        assert "9876543210" not in (record.previous_action or "")
        assert "[PHONE REMOVED]" in (record.previous_action or "")
