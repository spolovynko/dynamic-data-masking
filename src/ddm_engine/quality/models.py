from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, computed_field


class VerificationStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"


class VerificationLeak(BaseModel):
    decision_id: str
    label: str
    page_number: int
    text_hash: str


class VerificationReport(BaseModel):
    job_id: str
    status: VerificationStatus
    checked_decision_count: int
    checked_region_count: int
    leaks: list[VerificationLeak]

    @computed_field
    @property
    def leak_count(self) -> int:
        return len(self.leaks)
