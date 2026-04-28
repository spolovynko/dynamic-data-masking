from __future__ import annotations

import hashlib
import logging

from ddm_engine.config import Settings
from ddm_engine.llm.cache import InMemoryLLMCache
from ddm_engine.llm.client import LLMClientError, OllamaClient
from ddm_engine.llm.prompts import build_special_category_prompt
from ddm_engine.llm.safety import bounded_context
from ddm_engine.llm.schemas import LLMDetectionResponse
from ddm_engine.llm.validator import LLMValidationError, validate_detection_response
from ddm_engine.observability.metrics import LLM_JSON_VALIDATION_FAILURES_TOTAL

logger = logging.getLogger(__name__)


class SpecialCategoryDecisionEngine:
    def __init__(
        self,
        client: OllamaClient,
        max_context_chars: int,
        max_retries: int = 1,
        cache: InMemoryLLMCache | None = None,
    ) -> None:
        self.client = client
        self.max_context_chars = max_context_chars
        self.max_retries = max_retries
        self.cache = cache or InMemoryLLMCache()

    @classmethod
    def from_settings(cls, settings: Settings) -> SpecialCategoryDecisionEngine:
        return cls(
            client=OllamaClient.from_settings(settings),
            max_context_chars=settings.llm_max_context_chars,
        )

    def detect(self, text_window: str) -> LLMDetectionResponse:
        safe_context = bounded_context(text_window, self.max_context_chars)
        cache_key = hashlib.sha256(safe_context.encode()).hexdigest()
        raw_output = self.cache.get(cache_key)
        if raw_output is not None:
            return validate_detection_response(raw_output)

        prompt = build_special_category_prompt(safe_context)
        for _attempt in range(self.max_retries + 1):
            try:
                raw_output = self.client.generate_json(prompt)
                response = validate_detection_response(raw_output)
            except LLMValidationError:
                LLM_JSON_VALIDATION_FAILURES_TOTAL.inc()
                logger.warning("LLM detection response failed schema validation")
                prompt = (
                    f"{prompt}\n\nYour previous output was invalid. Return only valid JSON "
                    'matching {"findings":[...]} or {"findings":[]}.'
                )
                continue
            except LLMClientError:
                logger.warning("LLM provider request failed")
                return LLMDetectionResponse()

            self.cache.set(cache_key, raw_output)
            return response

        return LLMDetectionResponse()
