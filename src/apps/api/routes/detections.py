from fastapi import APIRouter, HTTPException, status

from apps.api.dependencies import AuthorizedJobDep, ObjectStoreDep, require_artifact
from apps.api.schemas.detections import (
    DetectionReviewRequest,
    DetectionReviewResponse,
    DetectionsResponse,
)
from ddm_engine.detection.review import DetectionReviewOverride, DetectionReviewStore
from ddm_engine.observability.metrics import HUMAN_OVERRIDES_TOTAL
from ddm_engine.storage.artifacts import ArtifactKeys, JsonArtifactStore

router = APIRouter(tags=["detections"])


@router.get("/jobs/{job_id}/detections", response_model=DetectionsResponse)
def get_detections(
    job: AuthorizedJobDep,
    object_store: ObjectStoreDep,
) -> DetectionsResponse:
    detections_key = ArtifactKeys.detections(job.job_id)
    require_artifact(object_store, detections_key, "Detections are not available for this job yet")

    payload = JsonArtifactStore(object_store).read_json(detections_key)
    return DetectionsResponse.model_validate(payload)


@router.patch(
    "/jobs/{job_id}/detections/{candidate_id}",
    response_model=DetectionReviewResponse,
)
def review_detection(
    candidate_id: str,
    request: DetectionReviewRequest,
    job: AuthorizedJobDep,
    object_store: ObjectStoreDep,
) -> DetectionReviewResponse:
    detections_key = ArtifactKeys.detections(job.job_id)
    require_artifact(object_store, detections_key, "Detections are not available for this job yet")

    detections = DetectionsResponse.model_validate_json(object_store.read_bytes(detections_key))
    if candidate_id not in {candidate.candidate_id for candidate in detections.candidates}:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Detection candidate not found: {candidate_id}",
        )

    override = DetectionReviewStore(object_store).upsert(
        job.job_id,
        DetectionReviewOverride(
            candidate_id=candidate_id,
            action=request.action,
            label=request.label,
            reason=request.reason,
        ),
    )
    HUMAN_OVERRIDES_TOTAL.labels(action=override.action.value).inc()
    return DetectionReviewResponse(**override.model_dump(mode="json"))
