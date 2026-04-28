from __future__ import annotations

from dataclasses import dataclass

from ddm_engine.storage.object_store import ObjectStore


@dataclass(frozen=True)
class CleanupResult:
    job_id: str
    deleted_prefixes: list[str]


JOB_ARTIFACT_PREFIXES = (
    "originals/{job_id}",
    "extracted/{job_id}",
    "detections/{job_id}",
    "reviews/{job_id}",
    "plans/{job_id}",
    "quality/{job_id}",
    "redacted/{job_id}",
)


def cleanup_job_artifacts(object_store: ObjectStore, job_id: str) -> CleanupResult:
    deleted: list[str] = []
    for prefix_template in JOB_ARTIFACT_PREFIXES:
        prefix = prefix_template.format(job_id=job_id)
        if hasattr(object_store, "delete_prefix"):
            object_store.delete_prefix(prefix)
            deleted.append(prefix)
    return CleanupResult(job_id=job_id, deleted_prefixes=deleted)
