"""
Tests for GuardrailService — all three RAI gates.
"""
import pytest
from services.guardrail_service import GuardrailService
from schemas.chat import ClassificationResult
from core.enums import CategoryType, IntentType, ScopeType


@pytest.fixture
def svc():
    return GuardrailService()


class TestGate1IsInScope:
    def test_water_campus_high_confidence(self, svc):
        cls = ClassificationResult(intent=IntentType.SOLUTION, category=CategoryType.WATER,
                                   scope=ScopeType.CAMPUS, confidence=0.92)
        assert svc.is_in_scope(cls) is True

    def test_air_city_in_scope(self, svc):
        cls = ClassificationResult(intent=IntentType.GUIDANCE, category=CategoryType.AIR,
                                   scope=ScopeType.CITY, confidence=0.80)
        assert svc.is_in_scope(cls) is True

    def test_waste_campus_in_scope(self, svc):
        cls = ClassificationResult(intent=IntentType.COMPLAINT, category=CategoryType.WASTE,
                                   scope=ScopeType.CAMPUS, confidence=0.75)
        assert svc.is_in_scope(cls) is True

    def test_no_category_is_out_of_scope(self, svc):
        cls = ClassificationResult(intent=IntentType.INFORMATION, category=None,
                                   scope=None, confidence=0.95)
        assert svc.is_in_scope(cls) is False

    def test_low_confidence_is_out_of_scope(self, svc):
        cls = ClassificationResult(intent=IntentType.SOLUTION, category=CategoryType.WATER,
                                   scope=ScopeType.CITY, confidence=0.20)
        assert svc.is_in_scope(cls) is False

    def test_boundary_confidence_exact_threshold(self, svc):
        # Exactly at threshold should pass (>= 0.35)
        cls = ClassificationResult(intent=IntentType.SOLUTION, category=CategoryType.AIR,
                                   scope=ScopeType.CAMPUS, confidence=0.35)
        assert svc.is_in_scope(cls) is True

    def test_just_below_threshold_fails(self, svc):
        cls = ClassificationResult(intent=IntentType.SOLUTION, category=CategoryType.AIR,
                                   scope=ScopeType.CAMPUS, confidence=0.34)
        assert svc.is_in_scope(cls) is False


class TestGate2OutputSafety:
    def test_safe_text_unchanged(self, svc):
        text = "You should report the leak to Campus Facilities immediately."
        assert svc.check_output_safety(text) == text

    def test_submitted_to_triggers_disclaimer(self, svc):
        text = "Your complaint has been submitted to the municipal corporation."
        result = svc.check_output_safety(text)
        assert "[CivicAI Note" in result

    def test_notified_the_triggers_disclaimer(self, svc):
        text = "We have notified the campus management about your issue."
        result = svc.check_output_safety(text)
        assert "[CivicAI Note" in result

    def test_authorities_have_been_triggers_disclaimer(self, svc):
        text = "The authorities have been informed and will take action."
        result = svc.check_output_safety(text)
        assert "[CivicAI Note" in result

    def test_was_sent_to_triggers_disclaimer(self, svc):
        text = "Your report was sent to the civic authority."
        result = svc.check_output_safety(text)
        assert "[CivicAI Note" in result

    def test_general_guidance_not_flagged(self, svc):
        text = "Check with the campus water board and follow their procedure."
        result = svc.check_output_safety(text)
        assert "[CivicAI Note" not in result

    def test_original_text_preserved_in_output(self, svc):
        text = "Your complaint has been submitted to the municipal corporation."
        result = svc.check_output_safety(text)
        # Original text should still be present; disclaimer is appended
        assert text in result


class TestGate3PIISanitization:
    def test_email_removed(self, svc):
        result = svc.sanitize_complaint_text("Contact me at user@example.com")
        assert "user@example.com" not in result
        assert "[EMAIL REMOVED]" in result

    def test_indian_mobile_removed(self, svc):
        result = svc.sanitize_complaint_text("Call me at 9876543210")
        assert "9876543210" not in result
        assert "[PHONE REMOVED]" in result

    def test_aadhaar_with_spaces_removed(self, svc):
        result = svc.sanitize_complaint_text("My Aadhaar is 1234 5678 9012")
        assert "1234 5678 9012" not in result
        assert "[ID REMOVED]" in result

    def test_aadhaar_without_spaces_removed(self, svc):
        result = svc.sanitize_complaint_text("ID:123456789012")
        assert "123456789012" not in result
        assert "[ID REMOVED]" in result

    def test_pan_card_removed(self, svc):
        result = svc.sanitize_complaint_text("My PAN is ABCDE1234F")
        assert "ABCDE1234F" not in result
        assert "[ID REMOVED]" in result

    def test_clean_text_unchanged(self, svc):
        text = "The pipe near Block C is leaking steadily for 3 days."
        assert svc.sanitize_complaint_text(text) == text

    def test_empty_string_returned_unchanged(self, svc):
        assert svc.sanitize_complaint_text("") == ""

    def test_multiple_pii_types_all_removed(self, svc):
        text = "Call 9876543210 or email admin@test.org about the leak"
        result = svc.sanitize_complaint_text(text)
        assert "9876543210" not in result
        assert "admin@test.org" not in result
        assert "[PHONE REMOVED]" in result
        assert "[EMAIL REMOVED]" in result
