from pydantic import BaseModel, computed_field

from ddm_engine.detection.review import ReviewAction
from ddm_engine.extraction.models import BoundingBox


class DetectionCandidateResponse(BaseModel):
    candidate_id: str
    label: str
    text: str
    detector: str
    confidence: float
    page_number: int
    start_char: int
    end_char: int
    token_ids: list[str]
    boxes: list[BoundingBox]
    needs_llm_review: bool


class DetectionsResponse(BaseModel):
    job_id: str
    candidates: list[DetectionCandidateResponse]

    @computed_field
    @property
    def candidate_count(self) -> int:
        return len(self.candidates)


class DetectionReviewRequest(BaseModel):
    action: ReviewAction
    label: str | None = None
    reason: str = "Human review override."


class DetectionReviewResponse(BaseModel):
    candidate_id: str
    action: ReviewAction
    label: str | None = None
    reason: str
