import json

from ddm_engine.detection.models import DetectionResult
from ddm_engine.detection.review import DetectionReviewStore, ReviewAction
from ddm_engine.extraction.models import DocumentLayout
from ddm_engine.planning.merger import DetectionMerger
from ddm_engine.planning.models import RedactionPlan
from ddm_engine.planning.planner import RedactionPlanner
from ddm_engine.storage.jobs import JobRecord
from ddm_engine.storage.object_store import ObjectStore


class RedactionPlanningService:
    def __init__(
        self,
        object_store: ObjectStore,
        merger: DetectionMerger | None = None,
        planner: RedactionPlanner | None = None,
    ) -> None:
        self.object_store = object_store
        self.merger = merger or DetectionMerger()
        self.planner = planner or RedactionPlanner()

    def plan(self, job: JobRecord) -> RedactionPlan:
        layout = DocumentLayout.model_validate_json(
            self.object_store.read_bytes(f"extracted/{job.job_id}/layout.json")
        )
        detection_result = DetectionResult.model_validate_json(
            self.object_store.read_bytes(f"detections/{job.job_id}/candidates.json")
        )
        candidates = self._apply_review_overrides(job.job_id, detection_result)
        decisions = self.merger.merge(job.job_id, candidates)
        plan = self.planner.plan(job.job_id, decisions, layout)

        with self.object_store.open_writer(f"plans/{job.job_id}/redaction_plan.json") as output:
            output.write(json.dumps(plan.model_dump(mode="json"), indent=2).encode("utf-8"))

        return plan

    def _apply_review_overrides(self, job_id: str, detection_result: DetectionResult):
        overrides = DetectionReviewStore(self.object_store).list(job_id)
        if not overrides:
            return detection_result.candidates

        reviewed = []
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
