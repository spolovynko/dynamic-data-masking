from ddm_engine.detection.models import CandidateEntity, DetectionResult
from ddm_engine.detection.review import DetectionReviewStore, ReviewAction
from ddm_engine.extraction.models import DocumentLayout
from ddm_engine.planning.merger import DetectionMerger
from ddm_engine.planning.models import RedactionPlan
from ddm_engine.planning.planner import RedactionPlanner
from ddm_engine.storage.artifacts import ArtifactKeys, JsonArtifactStore
from ddm_engine.storage.jobs import JobRecord
from ddm_engine.storage.object_store import ObjectStore


class RedactionPlanningService:
    def __init__(
        self,
        object_store: ObjectStore,
        merger: DetectionMerger | None = None,
        planner: RedactionPlanner | None = None,
        review_store: DetectionReviewStore | None = None,
    ) -> None:
        self.object_store = object_store
        self.artifacts = JsonArtifactStore(object_store)
        self.merger = merger or DetectionMerger()
        self.planner = planner or RedactionPlanner()
        self.review_store = review_store or DetectionReviewStore(object_store)

    def plan(self, job: JobRecord) -> RedactionPlan:
        layout = self.artifacts.read_model(ArtifactKeys.layout(job.job_id), DocumentLayout)
        detection_result = self.artifacts.read_model(
            ArtifactKeys.detections(job.job_id),
            DetectionResult,
        )
        candidates = self._apply_review_overrides(job.job_id, detection_result)
        decisions = self.merger.merge(job.job_id, candidates)
        plan = self.planner.plan(job.job_id, decisions, layout)
        self.artifacts.write_model(ArtifactKeys.redaction_plan(job.job_id), plan)
        return plan

    def _apply_review_overrides(
        self,
        job_id: str,
        detection_result: DetectionResult,
    ) -> list[CandidateEntity]:
        overrides = self.review_store.list(job_id)
        if not overrides:
            return detection_result.candidates

        reviewed: list[CandidateEntity] = []
        for candidate in detection_result.candidates:
            override = overrides.get(candidate.candidate_id)
            if override is None:
                reviewed.append(candidate)
                continue
            if override.action == ReviewAction.SKIP:
                continue
            reviewed.append(
                candidate.model_copy(
                    update={
                        "label": override.label or candidate.label,
                        "needs_llm_review": False,
                    }
                )
            )
        return reviewed
