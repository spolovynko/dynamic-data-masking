import json

from ddm_engine.config import Settings
from ddm_engine.detection.presidio_detector import PresidioDetector
from ddm_engine.detection.regex_detector import RegexDetector
from ddm_engine.detection.service import DetectionService
from ddm_engine.detection.text_index import build_page_text_indexes
from ddm_engine.extraction.models import BoundingBox, DocumentLayout, LayoutToken, PageLayout
from ddm_engine.storage.object_store import LocalObjectStore


def test_detection_service_writes_candidates_for_email(tmp_path) -> None:
    store = LocalObjectStore(tmp_path)
    job_id = "d" * 32
    layout = DocumentLayout(
        job_id=job_id,
        source_file_type="pdf",
        pages=[
            PageLayout(
                page_number=1,
                width=612,
                height=792,
                rotation=0,
                tokens=[
                    _token("p1-t1", "Contact", 10, 10, 50, 20),
                    _token("p1-t2", "jane@example.com", 55, 10, 150, 20),
                ],
            )
        ],
    )
    with store.open_writer(f"extracted/{job_id}/layout.json") as output:
        output.write(layout.model_dump_json().encode("utf-8"))

    result = DetectionService(store, presidio_detector=NoopPresidioDetector()).detect(_job(job_id))

    assert result.candidate_count >= 1
    assert any(candidate.label == "EMAIL_ADDRESS" for candidate in result.candidates)
    assert any(candidate.text == "jane@example.com" for candidate in result.candidates)

    candidates_json = json.loads(store.read_bytes(f"detections/{job_id}/candidates.json"))
    assert candidates_json["job_id"] == job_id
    assert len(candidates_json["candidates"]) >= 1


def test_regex_detector_does_not_duplicate_credit_card_as_phone() -> None:
    layout = DocumentLayout(
        job_id="job-1",
        source_file_type="pdf",
        pages=[
            PageLayout(
                page_number=1,
                width=612,
                height=792,
                rotation=0,
                tokens=[
                    _token("p1-t1", "Card", 10, 10, 35, 20),
                    _token("p1-t2", "4111", 40, 10, 65, 20),
                    _token("p1-t3", "1111", 70, 10, 95, 20),
                    _token("p1-t4", "1111", 100, 10, 125, 20),
                    _token("p1-t5", "1111", 130, 10, 155, 20),
                ],
            )
        ],
    )

    candidates = RegexDetector().detect("job-1", build_page_text_indexes(layout))
    labels = [candidate.label for candidate in candidates]

    assert "CREDIT_CARD" in labels
    assert "PHONE_NUMBER" not in labels


def test_presidio_detector_defaults_to_names_only() -> None:
    detector = PresidioDetector()

    assert detector.entities == ("PERSON",)


def test_detection_service_passes_configured_presidio_entities(tmp_path) -> None:
    store = LocalObjectStore(tmp_path)
    service = DetectionService(
        store,
        settings=Settings(DDM_PRESIDIO_ENABLED=True, DDM_PRESIDIO_ENTITIES="PERSON"),
    )

    assert service.presidio_detector is not None
    assert service.presidio_detector.entities == ("PERSON",)


def test_settings_parses_presidio_entities() -> None:
    settings = Settings(DDM_PRESIDIO_ENTITIES="PERSON, LOCATION")

    assert settings.resolved_presidio_entities == ("PERSON", "LOCATION")


class NoopPresidioDetector:
    def detect(self, job_id, indexes):
        return []


def _token(token_id: str, text: str, x0: float, y0: float, x1: float, y1: float) -> LayoutToken:
    return LayoutToken(
        token_id=token_id,
        page_number=1,
        text=text,
        bbox=BoundingBox(x0=x0, y0=y0, x1=x1, y1=y1),
    )


def _job(job_id: str):
    from datetime import UTC, datetime

    from ddm_engine.storage.jobs import JobRecord, JobStatus

    now = datetime.now(UTC)
    return JobRecord(
        job_id=job_id,
        status=JobStatus.DETECTING,
        original_filename="sample.pdf",
        original_object_key=f"originals/{job_id}/original.pdf",
        file_type="pdf",
        content_type="application/pdf",
        size_bytes=100,
        redacted_object_key=None,
        failure_reason=None,
        created_at=now,
        updated_at=now,
    )
