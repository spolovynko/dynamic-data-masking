from enum import StrEnum

from pydantic import BaseModel, computed_field

from ddm_engine.extraction.models import BoundingBox


class RedactionDecisionStatus(StrEnum):
    MASK = "mask"
    SKIP = "skip"


class RedactionDecision(BaseModel):
    decision_id: str
    status: RedactionDecisionStatus
    label: str
    text: str
    confidence: float
    page_number: int
    start_char: int
    end_char: int
    token_ids: list[str]
    boxes: list[BoundingBox]
    detector_names: list[str]
    source_candidate_ids: list[str]
    reason: str


class RedactionRegion(BaseModel):
    region_id: str
    decision_id: str
    label: str
    page_number: int
    bbox: BoundingBox
    source_candidate_ids: list[str]


class RedactionPlan(BaseModel):
    job_id: str
    decisions: list[RedactionDecision]
    regions: list[RedactionRegion]

    @computed_field
    @property
    def decision_count(self) -> int:
        return len(self.decisions)

    @computed_field
    @property
    def region_count(self) -> int:
        return len(self.regions)
