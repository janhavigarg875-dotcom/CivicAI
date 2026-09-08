"""
Tests for ConversationService — full phase-transition coverage.
LLM and RAG services are mocked; no real API calls made.
"""
import pytest
from unittest.mock import patch, MagicMock

from core.enums import ConversationPhase, CategoryType, IntentType, ScopeType
from schemas.chat import ChatRequest, ClassificationResult


# ---------------------------------------------------------------------------
# Helper: build a fresh ConversationService with mocked dependencies
# ---------------------------------------------------------------------------
def _make_service(mock_llm, mock_rag):
    from services.conversation_service import ConversationService
    return ConversationService()


WATER_CLS = ClassificationResult(
    intent=IntentType.SOLUTION,
    category=CategoryType.WATER,
    scope=ScopeType.CAMPUS,
    confidence=0.92,
)

GUIDANCE_TEXT = "Report the water leak to Campus Facilities immediately."
CHUNKS = ["Water leaks should be reported to campus facilities."]


@pytest.fixture
def patched_services():
    with patch("services.conversation_service.llm_service") as mock_llm, \
         patch("services.conversation_service.rag_service") as mock_rag, \
         patch("services.conversation_service.guardrail_service") as mock_guard:
        mock_llm.classify_intent.return_value = WATER_CLS
        mock_llm.generate_response.return_value = GUIDANCE_TEXT
        mock_rag.retrieve.return_value = CHUNKS
        mock_guard.is_in_scope.return_value = True
        mock_guard.check_output_safety.side_effect = lambda t: t  # pass-through
        yield mock_llm, mock_rag, mock_guard


@pytest.fixture
def svc(patched_services):
    from services.conversation_service import ConversationService
    return ConversationService()


class TestPhaseTransitions:
    """Test the full GUIDANCE → RESOLUTION_CHECK → COMPLAINT_OFFER → … → COMPLETE flow."""

    def test_guidance_phase_on_first_message(self, svc, patched_services):
        r = svc.process_message(ChatRequest(session_id="s1", message="Water leak in my dorm"))
        assert r.phase == ConversationPhase.RESOLUTION_CHECK.value
        assert GUIDANCE_TEXT in r.message
        assert "Has this information helped" in r.message

    def test_resolution_check_yes_leads_to_complete(self, svc, patched_services):
        svc.process_message(ChatRequest(session_id="s2", message="Water leak in my dorm"))
        r = svc.process_message(ChatRequest(session_id="s2", message="Yes, it is resolved now"))
        assert r.phase == ConversationPhase.COMPLETE.value
        assert "resolved" in r.message.lower() or "glad" in r.message.lower()

    def test_resolution_check_no_leads_to_complaint_offer(self, svc, patched_services):
        svc.process_message(ChatRequest(session_id="s3", message="Water leak in my dorm"))
        r = svc.process_message(ChatRequest(session_id="s3", message="No, still not fixed"))
        assert r.phase == ConversationPhase.COMPLAINT_OFFER.value
        assert "simulated" in r.message.lower()

    def test_complaint_offer_decline_leads_to_complete(self, svc, patched_services):
        svc.process_message(ChatRequest(session_id="s4", message="Water leak in my dorm"))
        svc.process_message(ChatRequest(session_id="s4", message="No, still not fixed"))
        r = svc.process_message(ChatRequest(session_id="s4", message="No, don't register"))
        assert r.phase == ConversationPhase.COMPLETE.value
        assert "cancel" in r.message.lower() or "no complaint" in r.message.lower()

    def test_full_detail_collection_flow(self, svc, patched_services):
        sid = "s5"
        svc.process_message(ChatRequest(session_id=sid, message="Water leak in my dorm"))
        svc.process_message(ChatRequest(session_id=sid, message="No, still happening"))
        svc.process_message(ChatRequest(session_id=sid, message="Yes, proceed"))

        # Collect 4 detail fields
        svc.process_message(ChatRequest(session_id=sid, message="Block C, Room 204"))   # location
        svc.process_message(ChatRequest(session_id=sid, message="3 days"))              # duration
        svc.process_message(ChatRequest(session_id=sid, message="Pipe dripping"))       # description
        r = svc.process_message(ChatRequest(session_id=sid, message="Told supervisor")) # previous_action

        assert r.phase == ConversationPhase.COMPLAINT_CONFIRM.value
        assert r.requires_confirmation is True
        assert r.complaint_draft is not None
        assert r.complaint_draft.get("location") == "Block C, Room 204"
        assert r.complaint_draft.get("duration") == "3 days"
        assert r.complaint_draft.get("description") == "Pipe dripping"
        assert r.complaint_draft.get("previous_action") == "Told supervisor"

    def test_complaint_confirm_cancel(self, svc, patched_services):
        sid = "s6"
        svc.process_message(ChatRequest(session_id=sid, message="Water leak"))
        svc.process_message(ChatRequest(session_id=sid, message="No"))
        svc.process_message(ChatRequest(session_id=sid, message="Yes"))
        svc.process_message(ChatRequest(session_id=sid, message="Block A"))
        svc.process_message(ChatRequest(session_id=sid, message="2 days"))
        svc.process_message(ChatRequest(session_id=sid, message="Constant drip"))
        svc.process_message(ChatRequest(session_id=sid, message="None"))
        r = svc.process_message(ChatRequest(session_id=sid, message="No, cancel"))
        assert r.phase == ConversationPhase.COMPLETE.value
        assert "cancel" in r.message.lower() or "no complaint" in r.message.lower()

    def test_complaint_confirm_yes_returns_sentinel(self, svc, patched_services):
        sid = "s7"
        svc.process_message(ChatRequest(session_id=sid, message="Water leak"))
        svc.process_message(ChatRequest(session_id=sid, message="No"))
        svc.process_message(ChatRequest(session_id=sid, message="Yes"))
        svc.process_message(ChatRequest(session_id=sid, message="Block B"))
        svc.process_message(ChatRequest(session_id=sid, message="1 week"))
        svc.process_message(ChatRequest(session_id=sid, message="Flooding floor"))
        svc.process_message(ChatRequest(session_id=sid, message="Reported before"))
        r = svc.process_message(ChatRequest(session_id=sid, message="Yes, confirm submission"))
        assert r.message == "__SUBMIT_COMPLAINT__"
        assert r.requires_confirmation is True
        assert r.complaint_draft is not None


class TestOutOfScope:
    """Test that out-of-scope messages are rejected gracefully."""

    def test_out_of_scope_stays_in_guidance(self):
        with patch("services.conversation_service.llm_service") as mock_llm, \
             patch("services.conversation_service.rag_service") as mock_rag, \
             patch("services.conversation_service.guardrail_service") as mock_guard:
            from core.enums import IntentType
            mock_llm.classify_intent.return_value = ClassificationResult(
                intent=IntentType.INFORMATION, category=None, scope=None, confidence=0.9
            )
            mock_guard.is_in_scope.return_value = False
            mock_guard.check_output_safety.side_effect = lambda t: t
            mock_rag.retrieve.return_value = []

            from services.conversation_service import ConversationService
            svc = ConversationService()
            r = svc.process_message(ChatRequest(session_id="oos1", message="What is the best pizza place?"))
            assert r.phase == ConversationPhase.GUIDANCE.value
            assert "Water" in r.message or "water" in r.message.lower()

    def test_low_confidence_classification_rejected(self):
        with patch("services.conversation_service.llm_service") as mock_llm, \
             patch("services.conversation_service.rag_service") as mock_rag, \
             patch("services.conversation_service.guardrail_service") as mock_guard:
            mock_llm.classify_intent.return_value = ClassificationResult(
                intent=IntentType.GUIDANCE, category=CategoryType.WATER,
                scope=ScopeType.CAMPUS, confidence=0.15
            )
            mock_guard.is_in_scope.return_value = False
            mock_guard.check_output_safety.side_effect = lambda t: t
            mock_rag.retrieve.return_value = []

            from services.conversation_service import ConversationService
            svc = ConversationService()
            r = svc.process_message(ChatRequest(session_id="oos2", message="something vague"))
            assert r.phase == ConversationPhase.GUIDANCE.value


class TestComplaintDirectIntent:
    """Test that COMPLAINT intent skips to COMPLAINT_OFFER immediately."""

    def test_complaint_intent_goes_to_complaint_offer(self):
        complaint_cls = ClassificationResult(
            intent=IntentType.COMPLAINT,
            category=CategoryType.AIR,
            scope=ScopeType.CITY,
            confidence=0.88,
        )
        with patch("services.conversation_service.llm_service") as mock_llm, \
             patch("services.conversation_service.rag_service") as mock_rag, \
             patch("services.conversation_service.guardrail_service") as mock_guard:
            mock_llm.classify_intent.return_value = complaint_cls
            mock_llm.generate_response.return_value = "Air quality guidance here."
            mock_rag.retrieve.return_value = []
            mock_guard.is_in_scope.return_value = True
            mock_guard.check_output_safety.side_effect = lambda t: t

            from services.conversation_service import ConversationService
            svc = ConversationService()
            r = svc.process_message(ChatRequest(session_id="cd1", message="I want to file a complaint about air pollution"))
            assert r.phase == ConversationPhase.COMPLAINT_OFFER.value
