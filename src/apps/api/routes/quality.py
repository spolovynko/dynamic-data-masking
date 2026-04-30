from fastapi import APIRouter

from apps.api.dependencies import AuthorizedJobDep, ObjectStoreDep, require_artifact
from ddm_engine.quality.models import VerificationReport
from ddm_engine.storage.artifacts import ArtifactKeys, JsonArtifactStore

router = APIRouter(tags=["quality"])


@router.get("/jobs/{job_id}/verification", response_model=VerificationReport)
def get_verification_report(
    job: AuthorizedJobDep,
    object_store: ObjectStoreDep,
) -> VerificationReport:
    key = ArtifactKeys.verification(job.job_id)
    require_artifact(object_store, key, "Verification report is not available for this job yet")
    return JsonArtifactStore(object_store).read_model(key, VerificationReport)
