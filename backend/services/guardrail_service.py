"""
GuardrailService — Responsible AI enforcement layer.

Three gates applied on every conversation turn:
  Gate 1 (input):  is_in_scope()          — rejects out-of-category requests
  Gate 2 (output): check_output_safety()  — strips/replaces unsafe LLM claims
  Gate 3 (store):  sanitize_complaint_text() — removes PII before DB persistence

All three are called explicitly from ConversationService and ComplaintService,
making the RAI enforcement visible and auditable rather than implicit.
"""
from __future__ import annotations

import logging
import re

from schemas.chat import ClassificationResult
from core.enums import CategoryType

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Confidence threshold — below this, treat classification as uncertain
# ---------------------------------------------------------------------------
_MIN_CONFIDENCE = 0.35

# ---------------------------------------------------------------------------
# PII patterns — stripped before any complaint field is stored
# ---------------------------------------------------------------------------
_PII_PATTERNS: list[tuple[str, str]] = [
    # Email addresses (run first — most specific)
    (r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", "[EMAIL REMOVED]"),
    # Aadhaar (12-digit Indian national ID) — groups of 4 with optional spaces/hyphens
    # Run before generic phone pattern to avoid false-positive overlap
    (r"\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b", "[ID REMOVED]"),
    # PAN card (India) — ABCDE1234F pattern
    (r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", "[ID REMOVED]"),
    # Passport-like patterns (1-2 uppercase letters + 7-8 digits)
    (r"\b[A-Z]{1,2}\d{7,8}\b", "[ID REMOVED]"),
    # Indian mobile numbers (10 digits starting with 6-9, optional +91 prefix)
    (r"\b(?:\+?91[\s\-]?)?[6-9]\d{9}\b", "[PHONE REMOVED]"),
    # International phone numbers with explicit + or country code prefix
    (r"\b\+[0-9]{1,3}[\s\-]?\(?\d{2,4}\)?[\s\-]?\d{3,5}[\s\-]?\d{3,5}\b", "[PHONE REMOVED]"),
]

# ---------------------------------------------------------------------------
# Phrases that falsely claim a real authority was contacted or real action taken
# ---------------------------------------------------------------------------
_UNSAFE_REAL_ACTION_PHRASES: list[str] = [
    "has been submitted to",
    "was submitted to",
    "has been sent to",
    "was sent to",
    "notified the",
    "has notified",
    "authorities have been",
    "authority has been",
    "municipal corporation has received",
    "campus management has received",
    "complaint has been filed with",
    "registered with the",
    "forwarded to the real",
    "actual authority",
]

_SAFE_REPLACEMENT = (
    "[CivicAI Note: This complaint is simulated. No real authority has been notified "
    "and no real action has been taken automatically.]"
)


class GuardrailService:

    # ------------------------------------------------------------------
    # Gate 1 — input scope check
    # ------------------------------------------------------------------
    @staticmethod
    def is_in_scope(classification: ClassificationResult) -> bool:
        """
        Return True only if the message belongs to a supported category
        with sufficient classification confidence.
        """
        if classification.category is None:
            return False
        try:
            CategoryType(classification.category)
        except ValueError:
            return False
        if classification.confidence < _MIN_CONFIDENCE:
            logger.debug(
                "Out-of-scope: low confidence %.2f for category %s",
                classification.confidence,
                classification.category,
            )
            return False
        return True

    # ------------------------------------------------------------------
    # Gate 2 — output safety check
    # ------------------------------------------------------------------
    @staticmethod
    def check_output_safety(response_text: str) -> str:
        """
        Scan the LLM-generated response for phrases that falsely claim
        a real complaint was submitted or a real authority was notified.
        Replace the entire sentence containing the phrase with a safe disclaimer.
        """
        text = response_text
        lower = text.lower()

        triggered = False
        for phrase in _UNSAFE_REAL_ACTION_PHRASES:
            if phrase in lower:
                logger.warning(
                    "Output safety: unsafe phrase detected — '%s'", phrase
                )
                triggered = True
                break

        if triggered:
            # Append disclaimer rather than silently removing content
            text = text + "\n\n" + _SAFE_REPLACEMENT

        return text

    # ------------------------------------------------------------------
    # Gate 3 — PII sanitization before storage
    # ------------------------------------------------------------------
    @staticmethod
    def sanitize_complaint_text(text: str) -> str:
        """
        Remove PII patterns from complaint free-text fields before
        they are persisted to the database.
        """
        if not text:
            return text
        sanitized = text
        for pattern, replacement in _PII_PATTERNS:
            original = sanitized
            sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE)
            if sanitized != original:
                logger.info("PII pattern '%s' sanitized from complaint text", pattern[:30])
        return sanitized


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
guardrail_service = GuardrailService()
