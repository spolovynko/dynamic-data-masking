from __future__ import annotations

from ddm_engine.observability.metrics import (
    REDACTION_VERIFICATION_TOTAL,
    SENSITIVE_TEXT_LEAKAGE_TOTAL,
)
from ddm_engine.planning.models import RedactionPlan
from ddm_engine.quality.models import VerificationReport, VerificationStatus
from ddm_engine.quality.verifier import RedactionVerifier
from ddm_engine.storage.artifacts import ArtifactKeys, JsonArtifactStore
from ddm_engine.storage.jobs import JobRecord
from ddm_engine.storage.object_store import ObjectStore


class RedactionQualityService:
    def __init__(
        self,
        object_store: ObjectStore,
        verifier: RedactionVerifier | None = None,
    ) -> None:
        self.object_store = object_store
        self.artifacts = JsonArtifactStore(object_store)
        self.verifier = verifier or RedactionVerifier()

    def verify(self, job: JobRecord, redacted_object_key: str) -> VerificationReport:
        plan = self.artifacts.read_model(ArtifactKeys.redaction_plan(job.job_id), RedactionPlan)
        report = self.verifier.verify(
            job_id=job.job_id,
            redacted_pdf_bytes=self.object_store.read_bytes(redacted_object_key),
            plan=plan,
        )
        for leak in report.leaks:
            SENSITIVE_TEXT_LEAKAGE_TOTAL.labels(label=leak.label).inc()
        REDACTION_VERIFICATION_TOTAL.labels(outcome=report.status.value).inc()

        self.artifacts.write_model(ArtifactKeys.verification(job.job_id), report)
        return report

    @staticmethod
    def passed(report: VerificationReport) -> bool:
        return report.status == VerificationStatus.PASSED
