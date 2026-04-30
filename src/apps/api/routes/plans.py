from fastapi import APIRouter

from apps.api.dependencies import AuthorizedJobDep, JobStoreDep, ObjectStoreDep, require_artifact
from ddm_engine.planning.models import RedactionPlan
from ddm_engine.planning.service import RedactionPlanningService
from ddm_engine.quality.service import RedactionQualityService
from ddm_engine.rendering.pdf_redactor import PDFRedactionService
from ddm_engine.storage.artifacts import ArtifactKeys, JsonArtifactStore
from ddm_engine.storage.jobs import JobStatus

router = APIRouter(tags=["redaction-plans"])


@router.get("/jobs/{job_id}/redaction-plan", response_model=RedactionPlan)
def get_redaction_plan(
    job: AuthorizedJobDep,
    object_store: ObjectStoreDep,
) -> RedactionPlan:
    plan_key = ArtifactKeys.redaction_plan(job.job_id)
    require_artifact(object_store, plan_key, "Redaction plan is not available for this job yet")

    payload = JsonArtifactStore(object_store).read_json(plan_key)
    return RedactionPlan.model_validate(payload)


@router.post("/jobs/{job_id}/redaction-plan/rebuild", response_model=RedactionPlan)
def rebuild_redaction_plan(
    job: AuthorizedJobDep,
    store: JobStoreDep,
    object_store: ObjectStoreDep,
) -> RedactionPlan:
    require_artifact(
        object_store,
        ArtifactKeys.detections(job.job_id),
        "Detections are not available for this job yet",
    )

    plan = RedactionPlanningService(object_store).plan(job)
    redacted_object_key = PDFRedactionService(object_store).redact(job)
    report = RedactionQualityService(object_store).verify(job, redacted_object_key)
    if RedactionQualityService.passed(report):
        store.update_redacted_output(job.job_id, redacted_object_key)
    else:
        store.update_status(
            job.job_id,
            status=JobStatus.FAILED_VERIFICATION,
            failure_reason="Sensitive text leakage detected after redaction",
        )
    return plan
