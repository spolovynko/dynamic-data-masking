from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from urllib.parse import urlparse

from ddm_engine.config import Settings
from ddm_engine.llm.prompts import SYSTEM_PROMPT
from ddm_engine.observability.metrics import LLM_CALLS_TOTAL, LLM_LATENCY_SECONDS


class LLMClientError(Exception):
    """Raised when an LLM provider call fails."""


@dataclass(frozen=True)
class OllamaClient:
    base_url: str
    model: str
    temperature: float = 0.0
    timeout_seconds: int = 60

    @classmethod
    def from_settings(cls, settings: Settings) -> OllamaClient:
        return cls(
            base_url=settings.ollama_base_url.rstrip("/"),
            model=settings.ollama_model,
            temperature=settings.llm_temperature,
            timeout_seconds=settings.llm_timeout_seconds,
        )

    def generate_json(self, prompt: str) -> str:
        endpoint = f"{self.base_url}/api/generate"
        if urlparse(endpoint).scheme not in {"http", "https"}:
            raise LLMClientError("Ollama base URL must use http or https")

        payload = {
            "model": self.model,
            "system": SYSTEM_PROMPT,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {"temperature": self.temperature},
        }
        request = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        started_at = time.perf_counter()
        try:
            with urllib.request.urlopen(  # nosec B310
                request,
                timeout=self.timeout_seconds,
            ) as response:
                response_payload = json.loads(response.read().decode())
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
            LLM_CALLS_TOTAL.labels(
                provider="ollama",
                model=self.model,
                outcome="error",
            ).inc()
            raise LLMClientError("Ollama request failed") from exc
        finally:
            LLM_LATENCY_SECONDS.labels(provider="ollama", model=self.model).observe(
                time.perf_counter() - started_at
            )

        generated = response_payload.get("response")
        if not isinstance(generated, str):
            LLM_CALLS_TOTAL.labels(
                provider="ollama",
                model=self.model,
                outcome="error",
            ).inc()
            raise LLMClientError("Ollama response did not contain generated text")
        LLM_CALLS_TOTAL.labels(provider="ollama", model=self.model, outcome="success").inc()
        return generated
