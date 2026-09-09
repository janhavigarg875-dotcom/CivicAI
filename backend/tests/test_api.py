"""
Integration tests for the FastAPI endpoints using httpx.AsyncClient.
LLM, RAG, and the RAG build() call are mocked to keep tests fast.
"""
import pytest
import pytest_asyncio
from unittest.mock import patch, MagicMock, AsyncMock

from fastapi.testclient import TestClient

from core.enums import CategoryType, IntentType, ScopeType
from schemas.chat import ClassificationResult


WATER_CLS = ClassificationResult(
    intent=IntentType.SOLUTION,
    category=CategoryType.WATER,
    scope=ScopeType.CAMPUS,
    confidence=0.92,
)

GUIDANCE = "Report the leak to Campus Facilities immediately."


@pytest.fixture(scope="module")
def test_client():
    """
    Create a TestClient with all external services mocked.
    RAG build() is skipped. DB uses a module-scoped in-memory SQLite.
    """
    from sqlalchemy import create_engine as _create_engine
    from sqlalchemy.orm import sessionmaker
    from db.database import Base, get_db
    import models.complaint  # noqa: F401

    # Create a single persistent in-memory engine for the whole module
    engine = _create_engine("sqlite:///./test_integration.db", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(bind=engine)

    def _override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    with patch("services.rag_service.RAGService.build"), \
         patch("services.conversation_service.llm_service") as mock_llm, \
         patch("services.conversation_service.rag_service") as mock_rag, \
         patch("services.conversation_service.guardrail_service") as mock_guard:

        mock_llm.classify_intent.return_value = WATER_CLS
        mock_llm.generate_response.return_value = GUIDANCE
        mock_rag.retrieve.return_value = ["Water leaks should be reported."]
        mock_guard.is_in_scope.return_value = True
        mock_guard.check_output_safety.side_effect = lambda t: t

        from main import app
        app.dependency_overrides[get_db] = _override_get_db

        with TestClient(app) as client:
            yield client

        app.dependency_overrides.clear()

    # Clean up the test DB file (best-effort — Windows may hold the lock briefly)
    import os, time
    for _ in range(3):
        try:
            os.remove("./test_integration.db")
            break
        except (FileNotFoundError, PermissionError):
            time.sleep(0.2)


class TestHealthEndpoint:
    def test_health_returns_ok(self, test_client):
        r = test_client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"
        assert r.json()["service"] == "CivicAI"


class TestChatEndpoint:
    def test_post_chat_returns_200(self, test_client):
        r = test_client.post("/api/chat", json={"session_id": "t1", "message": "Water leak in my dorm"})
        assert r.status_code == 200

    def test_chat_response_has_required_fields(self, test_client):
        r = test_client.post("/api/chat", json={"session_id": "t2", "message": "Water leak in my dorm"})
        data = r.json()
        assert "session_id" in data
        assert "message" in data
        assert "phase" in data

    def test_chat_response_contains_guidance(self, test_client):
        r = test_client.post("/api/chat", json={"session_id": "t3", "message": "Water leak in my dorm"})
        assert GUIDANCE in r.json()["message"]

    def test_chat_response_phase_is_resolution_check(self, test_client):
        r = test_client.post("/api/chat", json={"session_id": "t4", "message": "Water leak in my dorm"})
        assert r.json()["phase"] == "RESOLUTION_CHECK"

    def test_chat_empty_message_rejected(self, test_client):
        r = test_client.post("/api/chat", json={"session_id": "t5", "message": ""})
        assert r.status_code == 422  # Pydantic min_length=1 validation

    def test_chat_missing_session_id_rejected(self, test_client):
        r = test_client.post("/api/chat", json={"message": "Water leak"})
        assert r.status_code == 422


class TestComplaintsEndpoint:
    def test_post_complaint_confirmed_returns_201_or_200(self, test_client):
        payload = {
            "session_id": "c1",
            "category": "WATER",
            "scope": "CAMPUS",
            "issue_summary": "Pipe leak in dorm",
            "location": "Block C Room 204",
            "duration": "3 days",
            "description": "Constant drip",
            "previous_action": "Told supervisor",
            "confirmed": True,
        }
        r = test_client.post("/api/complaints", json=payload)
        assert r.status_code in (200, 201)
        data = r.json()
        assert "id" in data
        assert "CIV-CAMPUS-" in data["id"]
        assert "simulated" in data["message"].lower()

    def test_post_complaint_without_confirmation_rejected(self, test_client):
        payload = {
            "session_id": "c2",
            "category": "WATER",
            "scope": "CITY",
            "issue_summary": "Water outage",
            "location": "Main Road",
            "confirmed": False,
        }
        r = test_client.post("/api/complaints", json=payload)
        assert r.status_code == 400

    def test_get_complaint_status_found(self, test_client):
        # Register one first
        payload = {
            "session_id": "c3",
            "category": "AIR",
            "scope": "CITY",
            "issue_summary": "Air pollution near factory",
            "location": "Industrial Zone",
            "confirmed": True,
        }
        reg = test_client.post("/api/complaints", json=payload)
        complaint_id = reg.json()["id"]

        r = test_client.get(f"/api/complaints/{complaint_id}")
        assert r.status_code == 200
        data = r.json()
        assert data["id"] == complaint_id
        assert data["status"] == "OPEN"
        assert "disclaimer" in data

    def test_get_complaint_status_not_found(self, test_client):
        r = test_client.get("/api/complaints/CIV-CAMPUS-00000000-00000")
        assert r.status_code == 404
