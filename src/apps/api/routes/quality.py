from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from apps.api.auth import RequestActor, assert_job_access, get_request_actor
from ddm_engine.config import Settings
from ddm_engine.quality.models import VerificationReport
from ddm_engine.storage.jobs import JobNotFoundError, JobStore
from ddm_engine.storage.object_store import create_object_store

router = APIRouter(tags=["quality"])


@router.get("/jobs/{job_id}/verification", response_model=VerificationReport)
def get_verification_report(
    job_id: str,
    actor: Annotated[RequestActor, Depends(get_request_actor)],
) -> VerificationReport:
    store = JobStore.from_environment()
    try:
        job = store.get(job_id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    assert_job_access(job, actor)

    object_store = create_object_store(Settings())
    key = f"quality/{job_id}/verification.json"
    if not object_store.exists(key):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Verification report is not available for this job yet",
        )
    return VerificationReport.model_validate_json(object_store.read_bytes(key))
