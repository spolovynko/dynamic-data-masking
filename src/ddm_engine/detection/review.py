from __future__ import annotations

import json
from enum import StrEnum

from pydantic import BaseModel

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

    def list(self, job_id: str) -> dict[str, DetectionReviewOverride]:
        key = self._key(job_id)
        if not self.object_store.exists(key):
            return {}
        payload = json.loads(self.object_store.read_bytes(key))
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
        with self.object_store.open_writer(self._key(job_id)) as output:
            output.write(json.dumps(payload, indent=2).encode("utf-8"))
        return override

    @staticmethod
    def _key(job_id: str) -> str:
        return f"reviews/{job_id}/overrides.json"
