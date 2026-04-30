from __future__ import annotations

import json
from typing import Any, TypeVar

from pydantic import BaseModel

from ddm_engine.storage.object_store import ObjectStore

ModelT = TypeVar("ModelT", bound=BaseModel)


class ArtifactKeys:
    @staticmethod
    def layout(job_id: str) -> str:
        return f"extracted/{job_id}/layout.json"

    @staticmethod
    def detections(job_id: str) -> str:
        return f"detections/{job_id}/candidates.json"

    @staticmethod
    def review_overrides(job_id: str) -> str:
        return f"reviews/{job_id}/overrides.json"

    @staticmethod
    def redaction_plan(job_id: str) -> str:
        return f"plans/{job_id}/redaction_plan.json"

    @staticmethod
    def verification(job_id: str) -> str:
        return f"quality/{job_id}/verification.json"

    @staticmethod
    def redacted_pdf(job_id: str) -> str:
        return f"redacted/{job_id}/redacted.pdf"


class JsonArtifactStore:
    def __init__(self, object_store: ObjectStore) -> None:
        self.object_store = object_store

    def read_json(self, key: str) -> dict[str, Any]:
        return json.loads(self.object_store.read_bytes(key))

    def write_json(self, key: str, payload: dict[str, Any]) -> None:
        with self.object_store.open_writer(key) as output:
            output.write(json.dumps(payload, indent=2).encode("utf-8"))

    def read_model(self, key: str, model_type: type[ModelT]) -> ModelT:
        return model_type.model_validate_json(self.object_store.read_bytes(key))

    def write_model(self, key: str, model: BaseModel) -> None:
        with self.object_store.open_writer(key) as output:
            output.write(model.model_dump_json(indent=2).encode("utf-8"))
