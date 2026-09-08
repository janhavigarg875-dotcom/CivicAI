"""
Tests for WatsonxLLMService._parse_classification() and config loading.
No real API calls — only the parsing and configuration logic is tested.
"""
import pytest
from core.enums import CategoryType, IntentType, ScopeType
from services.llm_service import WatsonxLLMService


class TestParseClassification:
    """Unit tests for the JSON classification parser."""

    def test_valid_full_json(self):
        raw = '{"intent": "SOLUTION", "category": "WATER", "scope": "CAMPUS", "confidence": 0.95}'
        result = WatsonxLLMService._parse_classification(raw)
        assert result.intent == IntentType.SOLUTION
        assert result.category == CategoryType.WATER
        assert result.scope == ScopeType.CAMPUS
        assert result.confidence == pytest.approx(0.95)

    def test_valid_complaint_intent(self):
        raw = '{"intent": "COMPLAINT", "category": "AIR", "scope": "CITY", "confidence": 0.80}'
        result = WatsonxLLMService._parse_classification(raw)
        assert result.intent == IntentType.COMPLAINT
        assert result.category == CategoryType.AIR
        assert result.scope == ScopeType.CITY

    def test_valid_waste_guidance(self):
        raw = '{"intent": "GUIDANCE", "category": "WASTE", "scope": "CAMPUS", "confidence": 0.75}'
        result = WatsonxLLMService._parse_classification(raw)
        assert result.intent == IntentType.GUIDANCE
        assert result.category == CategoryType.WASTE
        assert result.scope == ScopeType.CAMPUS

    def test_null_category_and_scope(self):
        raw = '{"intent": "INFORMATION", "category": null, "scope": null, "confidence": 0.60}'
        result = WatsonxLLMService._parse_classification(raw)
        assert result.intent == IntentType.INFORMATION
        assert result.category is None
        assert result.scope is None

    def test_markdown_fenced_json(self):
        raw = '```json\n{"intent": "COMPLAINT", "category": "WASTE", "scope": "CITY", "confidence": 0.8}\n```'
        result = WatsonxLLMService._parse_classification(raw)
        assert result.intent == IntentType.COMPLAINT
        assert result.category == CategoryType.WASTE

    def test_invalid_json_falls_back(self):
        result = WatsonxLLMService._parse_classification("not json at all")
        assert result.intent == IntentType.INFORMATION
        assert result.category is None
        assert result.confidence == 0.0

    def test_unknown_intent_falls_back(self):
        raw = '{"intent": "UNKNOWN_INTENT", "category": "WATER", "scope": "CAMPUS", "confidence": 0.9}'
        result = WatsonxLLMService._parse_classification(raw)
        assert result.intent == IntentType.INFORMATION

    def test_unknown_category_returns_none(self):
        raw = '{"intent": "GUIDANCE", "category": "FIRE", "scope": "CAMPUS", "confidence": 0.9}'
        result = WatsonxLLMService._parse_classification(raw)
        assert result.category is None

    def test_unknown_scope_returns_none(self):
        raw = '{"intent": "GUIDANCE", "category": "AIR", "scope": "MOON", "confidence": 0.9}'
        result = WatsonxLLMService._parse_classification(raw)
        assert result.scope is None

    def test_confidence_clamped_above_one(self):
        raw = '{"intent": "INFORMATION", "category": null, "scope": null, "confidence": 1.5}'
        result = WatsonxLLMService._parse_classification(raw)
        assert result.confidence == pytest.approx(1.0)

    def test_confidence_clamped_below_zero(self):
        raw = '{"intent": "INFORMATION", "category": null, "scope": null, "confidence": -0.5}'
        result = WatsonxLLMService._parse_classification(raw)
        assert result.confidence == pytest.approx(0.0)

    def test_missing_confidence_defaults_to_one(self):
        raw = '{"intent": "GUIDANCE", "category": "AIR", "scope": "CITY"}'
        result = WatsonxLLMService._parse_classification(raw)
        assert result.confidence == pytest.approx(1.0)

    def test_complaint_status_intent(self):
        raw = '{"intent": "COMPLAINT_STATUS", "category": "WATER", "scope": "CITY", "confidence": 0.85}'
        result = WatsonxLLMService._parse_classification(raw)
        assert result.intent == IntentType.COMPLAINT_STATUS


class TestLLMServiceConfig:
    """Tests for config and lazy init behaviour."""

    def test_model_not_initialized_before_first_call(self):
        svc = WatsonxLLMService()
        assert svc._model is None

    def test_raises_on_missing_credentials(self):
        from unittest.mock import patch
        svc = WatsonxLLMService()
        with patch("services.llm_service.settings") as mock_settings:
            mock_settings.watsonx_api_key = ""
            mock_settings.watsonx_project_id = ""
            mock_settings.watsonx_url = "https://test.example.com"
            mock_settings.model_id = "ibm/granite-3-8b-instruct"
            with pytest.raises(RuntimeError, match="WATSONX_API_KEY"):
                svc._get_model()
