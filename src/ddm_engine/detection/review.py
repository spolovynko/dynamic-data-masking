from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel

from ddm_engine.storage.artifacts import ArtifactKeys, JsonArtifactStore
from ddm_engine.storage.object_store import ObjectStore


class ReviewAction(StrEnum):
    MASK = "mask"
    SKIP = "skip"


class DetectionReviewOverride(BaseModel):
    candidate_id: str
    action: ReviewAction
    label: str | None = None
    reason: str = "Human review override."


class DetectionReviewStore:
    def __init__(self, object_store: ObjectStore) -> None:
        self.object_store = object_store
        self.artifacts = JsonArtifactStore(object_store)

    def list(self, job_id: str) -> dict[str, DetectionReviewOverride]:
        key = ArtifactKeys.review_overrides(job_id)
        if not self.object_store.exists(key):
            return {}
        payload = self.artifacts.read_json(key)
        return {
            item["candidate_id"]: DetectionReviewOverride.model_validate(item)
            for item in payload.get("overrides", [])
        }

    def upsert(self, job_id: str, override: DetectionReviewOverride) -> DetectionReviewOverride:
        overrides = self.list(job_id)
        overrides[override.candidate_id] = override
        payload = {
            "job_id": job_id,
            "overrides": [item.model_dump(mode="json") for item in overrides.values()],
        }
        self.artifacts.write_json(ArtifactKeys.review_overrides(job_id), payload)
        return override
