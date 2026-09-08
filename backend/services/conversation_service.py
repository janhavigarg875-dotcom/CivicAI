"""
ConversationService — multi-turn session state machine.

Each conversation progresses through these phases (defined in core/enums.py):

  GUIDANCE          → user describes issue; LLM provides grounded guidance
  RESOLUTION_CHECK  → assistant asks "Has the problem been resolved?"
  COMPLAINT_OFFER   → user said "no" or "unresolved"; assistant offers to register a complaint
  DETAIL_COLLECTION → collecting: location, duration, description, previous_action
  COMPLAINT_CONFIRM → show full draft to user and ask for explicit confirmation
  COMPLETE          → complaint registered (or user declined / resolved)

RAI guarantees enforced here:
  - Complaint is NEVER submitted without the user explicitly confirming.
  - Out-of-scope messages return a polite refusal.
  - RESOLUTION_CHECK_SUFFIX is appended after every guidance response.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Optional

from core.enums import (
    CategoryType,
    ConversationPhase,
    IntentType,
    ScopeType,
)
from core.prompts import (
    OUT_OF_SCOPE_RESPONSE,
    RESOLUTION_CHECK_SUFFIX,
)
from schemas.chat import ChatRequest, ChatResponse, ClassificationResult
from services.guardrail_service import guardrail_service
from services.llm_service import llm_service
from services.rag_service import rag_service

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Keywords used for simple resolution-check detection
# (supplements LLM classification in RESOLUTION_CHECK phase)
# ---------------------------------------------------------------------------
import re as _re

def _kw_match(text: str, keywords: set) -> bool:
    """Match keywords with word-boundary awareness to avoid substring false positives."""
    for kw in keywords:
        # Multi-word phrases: substring match is fine
        # Single words: require word boundaries
        if " " in kw:
            if kw in text:
                return True
        else:
            if _re.search(r"\b" + _re.escape(kw) + r"\b", text):
                return True
    return False

_UNRESOLVED_KEYWORDS = {
    "no", "nope", "not resolved", "not fixed", "still", "ongoing",
    "not yet", "unresolved", "problem persists", "same issue", "still happening",
    "still there", "hasnt", "hasn't", "not helped", "didn't help", "did not help",
    "register", "complaint", "report", "escalate", "file",
}
_RESOLVED_KEYWORDS = {
    "yes", "yep", "yeah", "resolved", "fixed", "sorted", "done",
    "thank you", "thanks", "it worked", "problem solved", "no problem",
    "all good", "great", "perfect",
}

# Detail collection sequence — fields asked in order
_DETAIL_FIELDS: list[tuple[str, str]] = [
    ("location",        "Could you tell me the **exact location** of the issue? (e.g. building name, floor, street, area)"),
    ("duration",        "How long has this issue been occurring? (e.g. since yesterday, for 2 weeks)"),
    ("description",     "Please describe the problem in more detail. What have you observed?"),
    ("previous_action", "Have you taken any previous action or reported this before? If yes, what happened?"),
]


# ---------------------------------------------------------------------------
# Session state dataclass
# ---------------------------------------------------------------------------
@dataclass
class SessionState:
    session_id: str
    phase: ConversationPhase = ConversationPhase.GUIDANCE
    history: list[dict] = field(default_factory=list)
    classification: Optional[ClassificationResult] = None
    complaint_draft: dict = field(default_factory=dict)
    detail_field_index: int = 0   # which field in _DETAIL_FIELDS we are collecting next


# ---------------------------------------------------------------------------
# ConversationService
# ---------------------------------------------------------------------------
class ConversationService:
    """
    Manages all active conversation sessions in memory.
    Sessions are keyed by the client-supplied session_id UUID.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, SessionState] = {}

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------
    def process_message(self, request: ChatRequest) -> ChatResponse:
        """
        Main entry point. Advances the conversation state machine by one turn
        and returns a ChatResponse.
        """
        session = self._get_or_create(request.session_id)
        user_msg = request.message.strip()

        # Append user turn to history
        session.history.append({"role": "user", "content": user_msg})

        response = self._dispatch(session, user_msg)

        # Append assistant turn to history
        session.history.append({"role": "assistant", "content": response.message})
        return response

    # ------------------------------------------------------------------
    # Private: dispatch by phase
    # ------------------------------------------------------------------
    def _dispatch(self, session: SessionState, user_msg: str) -> ChatResponse:
        phase = session.phase

        if phase == ConversationPhase.GUIDANCE:
            return self._handle_guidance(session, user_msg)

        if phase == ConversationPhase.RESOLUTION_CHECK:
            return self._handle_resolution_check(session, user_msg)

        if phase == ConversationPhase.COMPLAINT_OFFER:
            return self._handle_complaint_offer(session, user_msg)

        if phase == ConversationPhase.DETAIL_COLLECTION:
            return self._handle_detail_collection(session, user_msg)

        if phase == ConversationPhase.COMPLAINT_CONFIRM:
            return self._handle_complaint_confirm(session, user_msg)

        # COMPLETE — start a fresh conversation
        session.phase = ConversationPhase.GUIDANCE
        session.classification = None
        session.complaint_draft = {}
        session.detail_field_index = 0
        return self._handle_guidance(session, user_msg)

    # ------------------------------------------------------------------
    # Phase: GUIDANCE
    # ------------------------------------------------------------------
    def _handle_guidance(self, session: SessionState, user_msg: str) -> ChatResponse:
        # 1. Classify
        classification = llm_service.classify_intent(user_msg, session.history)
        session.classification = classification

        # 2. RAI Gate 1 — scope check via GuardrailService
        if not guardrail_service.is_in_scope(classification):
            # Stay in GUIDANCE phase — don't advance
            return ChatResponse(
                session_id=session.session_id,
                message=OUT_OF_SCOPE_RESPONSE,
                classification=classification,
                phase=session.phase.value,
            )

        # 3. If user is directly asking for complaint status, handle it
        if classification.intent == IntentType.COMPLAINT_STATUS:
            return ChatResponse(
                session_id=session.session_id,
                message=(
                    "To check the status of a complaint, please provide your complaint ID "
                    "(format: CIV-XXXXX-XXXXXXXX-XXXXX). I'll look it up for you."
                ),
                classification=classification,
                phase=session.phase.value,
            )

        # 4. Retrieve KB context
        context_chunks = rag_service.retrieve(
            query=user_msg,
            category=classification.category.value if classification.category else None,
            scope=classification.scope.value if classification.scope else None,
            top_k=4,
        )

        # 5. Generate grounded response
        guidance_text = llm_service.generate_response(
            user_message=user_msg,
            context_chunks=context_chunks,
            conversation_history=session.history[:-1],  # exclude the just-appended user turn
            intent=classification.intent.value,
            category=classification.category.value if classification.category else None,
            scope=classification.scope.value if classification.scope else None,
        )

        # 6. RAI Gate 2 — output safety check via GuardrailService
        safe_guidance = guardrail_service.check_output_safety(guidance_text)

        # 7. Append resolution-check question
        full_response = safe_guidance + RESOLUTION_CHECK_SUFFIX

        # 7. If user explicitly wants to file a complaint, jump straight to detail collection
        if classification.intent == IntentType.COMPLAINT:
            session.phase = ConversationPhase.COMPLAINT_OFFER
            # pre-fill draft from what we know
            self._seed_draft(session, classification)
        else:
            session.phase = ConversationPhase.RESOLUTION_CHECK

        return ChatResponse(
            session_id=session.session_id,
            message=full_response,
            classification=classification,
            phase=session.phase.value,
        )

    # ------------------------------------------------------------------
    # Phase: RESOLUTION_CHECK
    # ------------------------------------------------------------------
    def _handle_resolution_check(self, session: SessionState, user_msg: str) -> ChatResponse:
        lower = user_msg.lower()

        resolved = _kw_match(lower, _RESOLVED_KEYWORDS)
        unresolved = _kw_match(lower, _UNRESOLVED_KEYWORDS)

        if resolved and not unresolved:
            session.phase = ConversationPhase.COMPLETE
            return ChatResponse(
                session_id=session.session_id,
                message=(
                    "I'm glad to hear the issue has been resolved! 🌱 "
                    "If you face any other environmental concerns in the future, feel free to return. "
                    "Together we're building more sustainable campuses and communities."
                ),
                classification=session.classification,
                phase=session.phase.value,
            )

        if unresolved or not resolved:
            # Treat ambiguous input as unresolved — safer for user
            session.phase = ConversationPhase.COMPLAINT_OFFER
            self._seed_draft(session, session.classification)
            return ChatResponse(
                session_id=session.session_id,
                message=(
                    "I'm sorry to hear the problem is still ongoing. "
                    "I can help you register a **simulated complaint** that will be logged in our system "
                    "and conceptually routed to the appropriate authority.\n\n"
                    "⚠️ *Please note: This is a simulation. No real complaint will be submitted "
                    "and no real authority will be notified.*\n\n"
                    "Would you like to proceed with registering a complaint? (Yes / No)"
                ),
                classification=session.classification,
                phase=session.phase.value,
            )

        # Fallback — ask again
        return ChatResponse(
            session_id=session.session_id,
            message="I didn't quite catch that. Has the issue been resolved? Please reply **Yes** or **No**.",
            classification=session.classification,
            phase=session.phase.value,
        )

    # ------------------------------------------------------------------
    # Phase: COMPLAINT_OFFER
    # ------------------------------------------------------------------
    def _handle_complaint_offer(self, session: SessionState, user_msg: str) -> ChatResponse:
        lower = user_msg.lower()
        yes = any(kw in lower for kw in {"yes", "yeah", "yep", "sure", "ok", "okay", "proceed", "register", "file"})
        no = any(kw in lower for kw in {"no", "nope", "cancel", "skip", "don't", "dont", "not now"})

        if no:
            session.phase = ConversationPhase.COMPLETE
            return ChatResponse(
                session_id=session.session_id,
                message=(
                    "Understood — no complaint will be registered. "
                    "If the issue persists or you change your mind, feel free to start a new conversation. "
                    "Take care!"
                ),
                classification=session.classification,
                phase=session.phase.value,
            )

        if yes or not no:
            # Advance to detail collection
            session.phase = ConversationPhase.DETAIL_COLLECTION
            session.detail_field_index = 0
            # Start collecting the first field
            return self._ask_next_detail(session)

        return ChatResponse(
            session_id=session.session_id,
            message="Would you like to register a complaint? Please reply **Yes** to proceed or **No** to cancel.",
            classification=session.classification,
            phase=session.phase.value,
        )

    # ------------------------------------------------------------------
    # Phase: DETAIL_COLLECTION
    # ------------------------------------------------------------------
    def _handle_detail_collection(self, session: SessionState, user_msg: str) -> ChatResponse:
        # Save the user's answer for the current field
        field_name, _ = _DETAIL_FIELDS[session.detail_field_index]
        session.complaint_draft[field_name] = user_msg
        session.detail_field_index += 1

        if session.detail_field_index < len(_DETAIL_FIELDS):
            return self._ask_next_detail(session)

        # All details collected — move to confirmation
        session.phase = ConversationPhase.COMPLAINT_CONFIRM
        return self._build_confirmation_prompt(session)

    def _ask_next_detail(self, session: SessionState) -> ChatResponse:
        _, question = _DETAIL_FIELDS[session.detail_field_index]
        return ChatResponse(
            session_id=session.session_id,
            message=question,
            classification=session.classification,
            phase=session.phase.value,
        )

    def _build_confirmation_prompt(self, session: SessionState) -> ChatResponse:
        draft = session.complaint_draft
        cls = session.classification
        category = cls.category.value if cls and cls.category else "N/A"
        scope = cls.scope.value if cls and cls.scope else "N/A"
        routed = (
            "Campus Management / Maintenance"
            if scope == "CAMPUS"
            else "Municipal / Civic Authority"
        )

        summary = (
            "Here is a summary of your complaint before submission:\n\n"
            f"| Field | Details |\n"
            f"|---|---|\n"
            f"| **Category** | {category} |\n"
            f"| **Scope** | {scope} |\n"
            f"| **Issue** | {draft.get('issue_summary', 'N/A')} |\n"
            f"| **Location** | {draft.get('location', 'N/A')} |\n"
            f"| **Duration** | {draft.get('duration', 'N/A')} |\n"
            f"| **Description** | {draft.get('description', 'N/A')} |\n"
            f"| **Previous Action** | {draft.get('previous_action', 'None taken')} |\n"
            f"| **Will be routed to** | {routed} |\n\n"
            "⚠️ **Important:** This complaint is **simulated**. It will be logged in the CivicAI system "
            "but will **not** be sent to any real authority. No real action will be taken automatically.\n\n"
            "Do you confirm submission? Reply **Yes** to submit or **No** to cancel."
        )

        return ChatResponse(
            session_id=session.session_id,
            message=summary,
            classification=cls,
            requires_confirmation=True,
            complaint_draft=dict(draft),
            phase=session.phase.value,
        )

    # ------------------------------------------------------------------
    # Phase: COMPLAINT_CONFIRM
    # ------------------------------------------------------------------
    def _handle_complaint_confirm(self, session: SessionState, user_msg: str) -> ChatResponse:
        lower = user_msg.lower()
        confirmed = any(kw in lower for kw in {"yes", "yeah", "yep", "confirm", "submit", "ok", "okay", "sure"})
        cancelled = any(kw in lower for kw in {"no", "nope", "cancel", "stop", "don't", "dont"})

        if cancelled:
            session.phase = ConversationPhase.COMPLETE
            return ChatResponse(
                session_id=session.session_id,
                message="Complaint submission cancelled. No complaint has been registered. If you need further assistance, feel free to start a new conversation.",
                classification=session.classification,
                phase=session.phase.value,
            )

        if confirmed:
            # Signal to the API layer that it should call ComplaintService.register()
            session.phase = ConversationPhase.COMPLETE
            return ChatResponse(
                session_id=session.session_id,
                message="__SUBMIT_COMPLAINT__",   # sentinel; API layer replaces this
                classification=session.classification,
                requires_confirmation=True,
                complaint_draft=dict(session.complaint_draft),
                phase=session.phase.value,
            )

        # Ambiguous — ask again
        return ChatResponse(
            session_id=session.session_id,
            message="Please reply **Yes** to confirm submission or **No** to cancel.",
            classification=session.classification,
            requires_confirmation=True,
            complaint_draft=dict(session.complaint_draft),
            phase=session.phase.value,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _get_or_create(self, session_id: str) -> SessionState:
        if session_id not in self._sessions:
            self._sessions[session_id] = SessionState(session_id=session_id)
        return self._sessions[session_id]

    @staticmethod
    def _seed_draft(session: SessionState, classification: Optional[ClassificationResult]) -> None:
        """Pre-populate complaint draft with known classification data."""
        if classification:
            if classification.category:
                session.complaint_draft["category"] = classification.category.value
            if classification.scope:
                session.complaint_draft["scope"] = classification.scope.value
            # issue_summary from the first user message in history
            if session.history:
                first_user = next(
                    (h["content"] for h in session.history if h["role"] == "user"), ""
                )
                session.complaint_draft.setdefault("issue_summary", first_user[:200])


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
conversation_service = ConversationService()
