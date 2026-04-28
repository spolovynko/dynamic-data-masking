import json

from pydantic import ValidationError

from ddm_engine.llm.schemas import LLMDetectionResponse


class LLMValidationError(Exception):
    """Raised when LLM output does not match the expected schema."""


def validate_detection_response(raw_output: str) -> LLMDetectionResponse:
    try:
        payload = json.loads(raw_output)
        return LLMDetectionResponse.model_validate(payload)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise LLMValidationError("Invalid LLM detection response") from exc
