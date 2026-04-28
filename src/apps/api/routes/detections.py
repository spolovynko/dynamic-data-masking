import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from apps.api.auth import RequestActor, assert_job_access, get_request_actor
from apps.api.schemas.detections import (
    DetectionReviewRequest,
    DetectionReviewResponse,
    DetectionsResponse,
)
from ddm_engine.config import Settings
from ddm_engine.detection.review import DetectionReviewOverride, DetectionReviewStore, ReviewAction
from ddm_engine.observability.metrics import HUMAN_OVERRIDES_TOTAL
from ddm_engine.storage.jobs import JobNotFoundError, JobStore
from ddm_engine.storage.object_store import create_object_store

router = APIRouter(tags=["detections"])


@router.get("/jobs/{job_id}/detections", response_model=DetectionsResponse)
def get_detections(
    job_id: str,
    actor: Annotated[RequestActor, Depends(get_request_actor)],
) -> DetectionsResponse:
    store = JobStore.from_environment()
    try:
        job = store.get(job_id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    assert_job_access(job, actor)

    object_store = create_object_store(Settings())
    detections_key = f"detections/{job_id}/candidates.json"
    if not object_store.exists(detections_key):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Detections are not available for this job yet",
        )

    payload = json.loads(object_store.read_bytes(detections_key))
    return DetectionsResponse.model_validate(payload)


@router.patch(
    "/jobs/{job_id}/detections/{candidate_id}",
    response_model=DetectionReviewResponse,
)
def review_detection(
    job_id: str,
    candidate_id: str,
    request: DetectionReviewRequest,
    actor: Annotated[RequestActor, Depends(get_request_actor)],
) -> DetectionReviewResponse:
    store = JobStore.from_environment()
    try:
        job = store.get(job_id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    assert_job_access(job, actor)

    object_store = create_object_store(Settings())
    detections_key = f"detections/{job_id}/candidates.json"
    if not object_store.exists(detections_key):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Detections are not available for this job yet",
        )

    detections = DetectionsResponse.model_validate_json(object_store.read_bytes(detections_key))
    if candidate_id not in {candidate.candidate_id for candidate in detections.candidates}:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Detection candidate not found: {candidate_id}",
        )

    try:
        action = ReviewAction(request.action)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Review action must be 'mask' or 'skip'",
        ) from exc

    override = DetectionReviewStore(object_store).upsert(
        job_id,
        DetectionReviewOverride(
            candidate_id=candidate_id,
            action=action,
            label=request.label,
            reason=request.reason,
        ),
    )
    HUMAN_OVERRIDES_TOTAL.labels(action=override.action.value).inc()
    return DetectionReviewResponse(**override.model_dump(mode="json"))
