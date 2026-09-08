"""
Shared fixtures and test utilities for CivicAI backend tests.

All fixtures mock external dependencies (LLM, RAG) so no real API
calls or model downloads happen during the test suite.
"""
import sys
import os

# Ensure the backend package root is on sys.path for all tests
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.database import Base
from core.enums import CategoryType, IntentType, ScopeType
from schemas.chat import ClassificationResult


# ---------------------------------------------------------------------------
# In-memory SQLite database fixture (isolated per test)
# ---------------------------------------------------------------------------
@pytest.fixture
def db_session():
    """Provides a fresh in-memory SQLite session for each test."""
    import models.complaint  # noqa: F401 — register ORM model
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


# ---------------------------------------------------------------------------
# Pre-built classification results for common scenarios
# ---------------------------------------------------------------------------
@pytest.fixture
def water_campus_cls():
    return ClassificationResult(
        intent=IntentType.SOLUTION,
        category=CategoryType.WATER,
        scope=ScopeType.CAMPUS,
        confidence=0.92,
    )


@pytest.fixture
def air_city_cls():
    return ClassificationResult(
        intent=IntentType.GUIDANCE,
        category=CategoryType.AIR,
        scope=ScopeType.CITY,
        confidence=0.88,
    )


@pytest.fixture
def out_of_scope_cls():
    return ClassificationResult(
        intent=IntentType.INFORMATION,
        category=None,
        scope=None,
        confidence=0.9,
    )


# ---------------------------------------------------------------------------
# Mocked LLM and RAG services
# ---------------------------------------------------------------------------
MOCK_GUIDANCE = "You should report the water leak to Campus Facilities immediately via the helpdesk."
MOCK_CHUNKS = ["Water leaks should be reported to campus facilities."]


@pytest.fixture
def mock_llm(water_campus_cls):
    """Patches the LLM service module-level singleton."""
    with patch("services.conversation_service.llm_service") as m:
        m.classify_intent.return_value = water_campus_cls
        m.generate_response.return_value = MOCK_GUIDANCE
        yield m


@pytest.fixture
def mock_rag():
    """Patches the RAG service module-level singleton."""
    with patch("services.conversation_service.rag_service") as m:
        m.retrieve.return_value = MOCK_CHUNKS
        yield m
