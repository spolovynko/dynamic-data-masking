import json
from datetime import UTC, datetime

from ddm_engine.detection.models import CandidateEntity, DetectionResult, DetectorName
from ddm_engine.detection.review import DetectionReviewOverride, DetectionReviewStore, ReviewAction
from ddm_engine.extraction.models import BoundingBox, DocumentLayout, LayoutToken, PageLayout
from ddm_engine.planning.merger import DetectionMerger
from ddm_engine.planning.service import RedactionPlanningService
from ddm_engine.storage.jobs import JobRecord, JobStatus
from ddm_engine.storage.object_store import LocalObjectStore


def test_detection_merger_prefers_email_over_nested_url() -> None:
    candidates = [
        _candidate("regex-email", "EMAIL_ADDRESS", "jane@example.com", DetectorName.REGEX, 0, 16),
        _candidate(
            "presidio-email",
            "EMAIL_ADDRESS",
            "jane@example.com",
            DetectorName.PRESIDIO,
            0,
            16,
        ),
        _candidate("presidio-url", "URL", "example.com", DetectorName.PRESIDIO, 5, 16),
    ]

    decisions = DetectionMerger().merge("job-1", candidates)

    assert len(decisions) == 1
    assert decisions[0].label == "EMAIL_ADDRESS"
    assert decisions[0].text == "jane@example.com"
    assert decisions[0].detector_names == ["presidio", "regex"]
    assert len(decisions[0].source_candidate_ids) == 3


def test_detection_merger_prefers_llm_sensitive_phrase_over_nested_presidio_hit() -> None:
    candidates = [
        _candidate("presidio-nrp", "NRP", "scan", DetectorName.PRESIDIO, 12, 16),
        _candidate(
            "llm-biometric",
            "BIOMETRIC_DATA",
            "fingerprint scan access",
            DetectorName.LLM,
            0,
            23,
        ),
    ]

    decisions = DetectionMerger().merge("job-1", candidates)

    assert len(decisions) == 1
    assert decisions[0].label == "BIOMETRIC_DATA"
    assert decisions[0].text == "fingerprint scan access"


def test_redaction_planning_service_writes_plan_artifact(tmp_path) -> None:
    job_id = "e" * 32
    store = LocalObjectStore(tmp_path)
    layout = DocumentLayout(
        job_id=job_id,
        source_file_type="pdf",
        pages=[
            PageLayout(
                page_number=1,
                width=100,
                height=100,
                rotation=0,
                tokens=[_token("p1-t1", "jane@example.com", 1, 2, 20, 10)],
            )
        ],
    )
    detections = DetectionResult(
        job_id=job_id,
        candidates=[
            _candidate(
                "regex-email",
                "EMAIL_ADDRESS",
                "jane@example.com",
                DetectorName.REGEX,
                0,
                16,
            )
        ],
    )
    with store.open_writer(f"extracted/{job_id}/layout.json") as output:
        output.write(layout.model_dump_json().encode("utf-8"))
    with store.open_writer(f"detections/{job_id}/candidates.json") as output:
        output.write(detections.model_dump_json().encode("utf-8"))

    plan = RedactionPlanningService(store).plan(_job(job_id))

    assert plan.decision_count == 1
    assert plan.region_count == 1
    assert plan.regions[0].bbox.x0 == 0
    assert plan.regions[0].bbox.y0 == 0.5

    payload = json.loads(store.read_bytes(f"plans/{job_id}/redaction_plan.json"))
    assert payload["job_id"] == job_id
    assert payload["decision_count"] == 1
    assert payload["region_count"] == 1


def test_redaction_planning_service_applies_skip_override(tmp_path) -> None:
    job_id = "a" * 32
    store = LocalObjectStore(tmp_path)
    layout = DocumentLayout(
        job_id=job_id,
        source_file_type="pdf",
        pages=[
            PageLayout(
                page_number=1,
                width=100,
                height=100,
                rotation=0,
                tokens=[_token("p1-t1", "jane@example.com", 1, 2, 20, 10)],
            )
        ],
    )
    detections = DetectionResult(
        job_id=job_id,
        candidates=[
            _candidate(
                "regex-email",
                "EMAIL_ADDRESS",
                "jane@example.com",
                DetectorName.REGEX,
                0,
                16,
            )
        ],
    )
    with store.open_writer(f"extracted/{job_id}/layout.json") as output:
        output.write(layout.model_dump_json().encode("utf-8"))
    with store.open_writer(f"detections/{job_id}/candidates.json") as output:
        output.write(detections.model_dump_json().encode("utf-8"))
    DetectionReviewStore(store).upsert(
        job_id,
        DetectionReviewOverride(candidate_id="regex-email", action=ReviewAction.SKIP),
    )

    plan = RedactionPlanningService(store).plan(_job(job_id))

    assert plan.decisions == []
    assert plan.regions == []


def _candidate(
    candidate_id: str,
    label: str,
    text: str,
    detector: DetectorName,
    start: int,
    end: int,
) -> CandidateEntity:
    return CandidateEntity(
        candidate_id=candidate_id,
        label=label,
        text=text,
        detector=detector,
        confidence=0.9,
        page_number=1,
        start_char=start,
        end_char=end,
        token_ids=["p1-t1"],
        boxes=[BoundingBox(x0=1, y0=2, x1=20, y1=10)],
        needs_llm_review=False,
    )


def _token(token_id: str, text: str, x0: float, y0: float, x1: float, y1: float) -> LayoutToken:
    return LayoutToken(
        token_id=token_id,
        page_number=1,
        text=text,
        bbox=BoundingBox(x0=x0, y0=y0, x1=x1, y1=y1),
    )


def _job(job_id: str) -> JobRecord:
    now = datetime.now(UTC)
    return JobRecord(
        job_id=job_id,
        status=JobStatus.PLANNING_REDACTIONS,
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
