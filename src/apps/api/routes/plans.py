import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from apps.api.auth import RequestActor, assert_job_access, get_request_actor
from ddm_engine.config import Settings
from ddm_engine.planning.models import RedactionPlan
from ddm_engine.planning.service import RedactionPlanningService
from ddm_engine.quality.service import RedactionQualityService
from ddm_engine.rendering.pdf_redactor import PDFRedactionService
from ddm_engine.storage.jobs import JobNotFoundError, JobStatus, JobStore
from ddm_engine.storage.object_store import create_object_store

router = APIRouter(tags=["redaction-plans"])


@router.get("/jobs/{job_id}/redaction-plan", response_model=RedactionPlan)
def get_redaction_plan(
    job_id: str,
    actor: Annotated[RequestActor, Depends(get_request_actor)],
) -> RedactionPlan:
    store = JobStore.from_environment()
    try:
        job = store.get(job_id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    assert_job_access(job, actor)

    object_store = create_object_store(Settings())
    plan_key = f"plans/{job_id}/redaction_plan.json"
    if not object_store.exists(plan_key):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Redaction plan is not available for this job yet",
        )

    payload = json.loads(object_store.read_bytes(plan_key))
    return RedactionPlan.model_validate(payload)


@router.post("/jobs/{job_id}/redaction-plan/rebuild", response_model=RedactionPlan)
def rebuild_redaction_plan(
    job_id: str,
    actor: Annotated[RequestActor, Depends(get_request_actor)],
) -> RedactionPlan:
    store = JobStore.from_environment()
    try:
        job = store.get(job_id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    assert_job_access(job, actor)

    object_store = create_object_store(Settings())
    if not object_store.exists(f"detections/{job_id}/candidates.json"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Detections are not available for this job yet",
        )

    plan = RedactionPlanningService(object_store).plan(job)
    redacted_object_key = PDFRedactionService(object_store).redact(job)
    report = RedactionQualityService(object_store).verify(job, redacted_object_key)
    if RedactionQualityService.passed(report):
        store.update_redacted_output(job_id, redacted_object_key)
    else:
        store.update_status(
            job_id,
            status=JobStatus.FAILED_VERIFICATION,
            failure_reason="Sensitive text leakage detected after redaction",
        )
    return plan
