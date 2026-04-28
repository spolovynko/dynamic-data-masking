from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class SensitiveCategory(StrEnum):
    SEXUAL_ORIENTATION = "SEXUAL_ORIENTATION"
    RELIGION_OR_BELIEF = "RELIGION_OR_BELIEF"
    POLITICAL_BELIEF = "POLITICAL_BELIEF"
    TRADE_UNION_MEMBERSHIP = "TRADE_UNION_MEMBERSHIP"
    HEALTH_DATA = "HEALTH_DATA"
    RACIAL_OR_ETHNIC_ORIGIN = "RACIAL_OR_ETHNIC_ORIGIN"
    NATIONALITY_OR_NATIONAL_ORIGIN = "NATIONALITY_OR_NATIONAL_ORIGIN"
    PHYSICAL_ADDRESS = "PHYSICAL_ADDRESS"
    CRIMINAL_HISTORY = "CRIMINAL_HISTORY"
    BIOMETRIC_DATA = "BIOMETRIC_DATA"
    CONFIDENTIAL_CONTEXT = "CONFIDENTIAL_CONTEXT"


class LLMFinding(BaseModel):
    text: str = Field(min_length=1)
    label: SensitiveCategory
    should_mask: bool
    confidence: float = Field(ge=0.0, le=1.0)
    risk_level: Literal["low", "medium", "high"]
    reason: str = Field(max_length=500)

    @field_validator("reason", mode="before")
    @classmethod
    def normalize_reason(cls, value: Any) -> str:
        if isinstance(value, str) and value.strip():
            return value
        return "Model did not provide a reason."


class LLMDetectionResponse(BaseModel):
    findings: list[LLMFinding] = Field(default_factory=list)
