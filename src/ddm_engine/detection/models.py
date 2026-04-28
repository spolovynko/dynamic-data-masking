from enum import StrEnum

from pydantic import BaseModel, Field

from ddm_engine.extraction.models import BoundingBox


class DetectorName(StrEnum):
    REGEX = "regex"
    PRESIDIO = "presidio"
    LLM = "llm"


class CandidateEntity(BaseModel):
    candidate_id: str
    label: str
    text: str
    detector: DetectorName
    confidence: float = Field(ge=0.0, le=1.0)
    page_number: int
    start_char: int
    end_char: int
    token_ids: list[str]
    boxes: list[BoundingBox]
    needs_llm_review: bool = False


class DetectionResult(BaseModel):
    job_id: str
    candidates: list[CandidateEntity]

    @property
    def candidate_count(self) -> int:
        return len(self.candidates)
