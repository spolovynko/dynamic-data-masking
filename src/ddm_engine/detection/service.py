import json

from ddm_engine.config import Settings
from ddm_engine.detection.llm_detector import LLMSpecialCategoryDetector
from ddm_engine.detection.models import DetectionResult
from ddm_engine.detection.presidio_detector import PresidioDetector
from ddm_engine.detection.regex_detector import RegexDetector
from ddm_engine.detection.text_index import build_page_text_indexes
from ddm_engine.extraction.models import DocumentLayout
from ddm_engine.llm.decision_engine import SpecialCategoryDecisionEngine
from ddm_engine.llm.router import llm_special_category_detection_enabled
from ddm_engine.observability.metrics import ENTITIES_DETECTED_TOTAL
from ddm_engine.storage.jobs import JobRecord
from ddm_engine.storage.object_store import ObjectStore


class DetectionService:
    def __init__(
        self,
        object_store: ObjectStore,
        regex_detector: RegexDetector | None = None,
        presidio_detector: PresidioDetector | None = None,
        llm_detector: LLMSpecialCategoryDetector | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or Settings()
        self.object_store = object_store
        self.regex_detector = regex_detector or RegexDetector()
        self.presidio_detector = presidio_detector or (
            PresidioDetector(entities=self.settings.resolved_presidio_entities)
            if self.settings.presidio_enabled
            else None
        )
        self.llm_detector = llm_detector or (
            LLMSpecialCategoryDetector(SpecialCategoryDecisionEngine.from_settings(self.settings))
            if llm_special_category_detection_enabled(self.settings)
            else None
        )

    def detect(self, job: JobRecord) -> DetectionResult:
        layout_key = f"extracted/{job.job_id}/layout.json"
        layout = DocumentLayout.model_validate_json(self.object_store.read_bytes(layout_key))
        indexes = build_page_text_indexes(layout)

        candidates = [
            *self.regex_detector.detect(job.job_id, indexes),
        ]
        if self.presidio_detector is not None:
            candidates.extend(self.presidio_detector.detect(job.job_id, indexes))
        if self.llm_detector is not None:
            candidates.extend(self.llm_detector.detect(job.job_id, indexes))
        result = DetectionResult(job_id=job.job_id, candidates=candidates)
        for candidate in candidates:
            ENTITIES_DETECTED_TOTAL.labels(
                label=candidate.label,
                detector=candidate.detector.value,
            ).inc()

        with self.object_store.open_writer(f"detections/{job.job_id}/candidates.json") as output:
            output.write(json.dumps(result.model_dump(mode="json"), indent=2).encode("utf-8"))

        return result
