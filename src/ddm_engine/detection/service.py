from typing import Protocol

from ddm_engine.config import Settings
from ddm_engine.detection.llm_detector import LLMSpecialCategoryDetector
from ddm_engine.detection.models import CandidateEntity, DetectionResult
from ddm_engine.detection.presidio_detector import PresidioDetector
from ddm_engine.detection.regex_detector import RegexDetector
from ddm_engine.detection.text_index import build_page_text_indexes
from ddm_engine.extraction.models import DocumentLayout
from ddm_engine.llm.decision_engine import SpecialCategoryDecisionEngine
from ddm_engine.llm.router import llm_special_category_detection_enabled
from ddm_engine.observability.metrics import ENTITIES_DETECTED_TOTAL
from ddm_engine.storage.artifacts import ArtifactKeys, JsonArtifactStore
from ddm_engine.storage.jobs import JobRecord
from ddm_engine.storage.object_store import ObjectStore


class EntityDetector(Protocol):
    def detect(self, job_id: str, indexes) -> list[CandidateEntity]:
        raise NotImplementedError


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
        self.artifacts = JsonArtifactStore(object_store)
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
        layout = self.artifacts.read_model(ArtifactKeys.layout(job.job_id), DocumentLayout)
        indexes = build_page_text_indexes(layout)

        candidates = [
            candidate
            for detector in self._enabled_detectors()
            for candidate in detector.detect(job.job_id, indexes)
        ]
        result = DetectionResult(job_id=job.job_id, candidates=candidates)
        self._record_metrics(candidates)
        self.artifacts.write_model(ArtifactKeys.detections(job.job_id), result)
        return result

    def _enabled_detectors(self) -> tuple[EntityDetector, ...]:
        return tuple(
            detector
            for detector in (self.regex_detector, self.presidio_detector, self.llm_detector)
            if detector is not None
        )

    def _record_metrics(self, candidates: list[CandidateEntity]) -> None:
        for candidate in candidates:
            ENTITIES_DETECTED_TOTAL.labels(
                label=candidate.label,
                detector=candidate.detector.value,
            ).inc()
