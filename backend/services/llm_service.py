"""
WatsonxLLMService — wraps all IBM watsonx.ai API calls.

Two public methods:
  - classify_intent(user_message, history) -> ClassificationResult
  - generate_response(user_message, context_chunks, history, classification) -> str

Both methods are stateless; session history is passed in from ConversationService.
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from ibm_watsonx_ai import Credentials
from ibm_watsonx_ai.foundation_models import ModelInference

from core.config import settings
from core.prompts import (
    CLASSIFICATION_PROMPT_TEMPLATE,
    FALLBACK_RESPONSE,
    SYSTEM_PROMPT,
    build_response_prompt,
)
from schemas.chat import ClassificationResult
from core.enums import CategoryType, IntentType, ScopeType

logger = logging.getLogger(__name__)

# JSON schema used to coerce the model into returning valid classification JSON
_CLASSIFICATION_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {
            "type": "string",
            "enum": ["INFORMATION", "GUIDANCE", "SOLUTION", "COMPLAINT", "COMPLAINT_STATUS"],
        },
        "category": {
            "type": ["string", "null"],
            "enum": ["WATER", "AIR", "WASTE", None],
        },
        "scope": {
            "type": ["string", "null"],
            "enum": ["CAMPUS", "CITY", None],
        },
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
    },
    "required": ["intent", "confidence"],
}


class WatsonxLLMService:
    """
    Thin wrapper around ibm-watsonx-ai ModelInference.
    Initialisation is lazy — credentials are validated on first call, not at import time,
    so the app starts fine even without a .env populated (useful for tests).
    """

    def __init__(self) -> None:
        self._model: Optional[ModelInference] = None

    def _get_model(self) -> ModelInference:
        """Lazy-init the ModelInference client."""
        if self._model is None:
            if not settings.watsonx_api_key or not settings.watsonx_project_id:
                raise RuntimeError(
                    "WATSONX_API_KEY and WATSONX_PROJECT_ID must be set in .env "
                    "before making LLM calls."
                )
            credentials = Credentials(
                url=settings.watsonx_url,
                api_key=settings.watsonx_api_key,
            )
            self._model = ModelInference(
                model_id=settings.model_id,
                credentials=credentials,
                project_id=settings.watsonx_project_id,
            )
            logger.info("WatsonxLLMService initialised with model: %s", settings.model_id)
        return self._model

    # ------------------------------------------------------------------
    # Public: classify_intent
    # ------------------------------------------------------------------
    def classify_intent(
        self,
        user_message: str,
        conversation_history: list[dict],
    ) -> ClassificationResult:
        """
        Ask the model to classify the user message and return a ClassificationResult.
        Uses guided JSON output (response_format) for deterministic parsing.
        Falls back to INFORMATION / null / null on any failure.
        """
        prompt = CLASSIFICATION_PROMPT_TEMPLATE.format(user_message=user_message)

        # Include last 2 turns of history for context-aware classification
        messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
        for turn in conversation_history[-2:]:
            messages.append({"role": turn["role"], "content": turn["content"]})
        messages.append({"role": "user", "content": prompt})

        params = {
            "temperature": settings.classify_temperature,
            "max_completion_tokens": settings.classify_max_new_tokens,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "classification",
                    "schema": _CLASSIFICATION_JSON_SCHEMA,
                    "strict": False,
                },
            },
        }

        try:
            model = self._get_model()
            response = model.chat(messages=messages, params=params)
            raw_text = response["choices"][0]["message"]["content"].strip()
            return self._parse_classification(raw_text)
        except RuntimeError:
            raise  # propagate config errors so they surface clearly
        except Exception as exc:
            logger.error("classify_intent failed: %s", exc, exc_info=True)
            return ClassificationResult(
                intent=IntentType.INFORMATION,
                category=None,
                scope=None,
                confidence=0.0,
            )

    # ------------------------------------------------------------------
    # Public: generate_response
    # ------------------------------------------------------------------
    def generate_response(
        self,
        user_message: str,
        context_chunks: list[str],
        conversation_history: list[dict],
        intent: str,
        category: Optional[str],
        scope: Optional[str],
    ) -> str:
        """
        Generate a grounded natural-language response using retrieved KB context.
        Returns FALLBACK_RESPONSE on any API error.
        """
        messages = build_response_prompt(
            user_message=user_message,
            context_chunks=context_chunks,
            conversation_history=conversation_history,
            intent=intent,
            category=category,
            scope=scope,
        )

        params = {
            "temperature": settings.temperature,
            "top_p": settings.top_p,
            "max_completion_tokens": settings.max_new_tokens,
        }

        try:
            model = self._get_model()
            response = model.chat(messages=messages, params=params)
            return response["choices"][0]["message"]["content"].strip()
        except RuntimeError:
            raise
        except Exception as exc:
            logger.error("generate_response failed: %s", exc, exc_info=True)
            return FALLBACK_RESPONSE

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _parse_classification(raw_text: str) -> ClassificationResult:
        """
        Parse the model's JSON output into a ClassificationResult.
        Strips markdown fences if the model wrapped the JSON anyway.
        """
        text = raw_text.strip()
        # Strip optional ```json ... ``` fences
        if text.startswith("```"):
            lines = text.splitlines()
            text = "\n".join(
                line for line in lines
                if not line.strip().startswith("```")
            ).strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            logger.warning("Classification JSON parse failed: %s | raw: %r", exc, raw_text)
            return ClassificationResult(
                intent=IntentType.INFORMATION,
                category=None,
                scope=None,
                confidence=0.0,
            )

        # Safely map string values to enums
        intent_val = data.get("intent", "INFORMATION")
        try:
            intent = IntentType(intent_val)
        except ValueError:
            intent = IntentType.INFORMATION

        category_val = data.get("category")
        category: Optional[CategoryType] = None
        if category_val:
            try:
                category = CategoryType(category_val)
            except ValueError:
                category = None

        scope_val = data.get("scope")
        scope: Optional[ScopeType] = None
        if scope_val:
            try:
                scope = ScopeType(scope_val)
            except ValueError:
                scope = None

        confidence = float(data.get("confidence", 1.0))
        confidence = max(0.0, min(1.0, confidence))

        return ClassificationResult(
            intent=intent,
            category=category,
            scope=scope,
            confidence=confidence,
        )


# Module-level singleton — imported by ConversationService
llm_service = WatsonxLLMService()
