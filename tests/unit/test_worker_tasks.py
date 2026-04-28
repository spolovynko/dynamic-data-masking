import json
from datetime import UTC, datetime

import fitz

from apps.worker.tasks import process_document
from ddm_engine.config import Settings
from ddm_engine.detection.models import DetectionResult
from ddm_engine.storage.jobs import JobRecord, JobStatus
from ddm_engine.storage.object_store import create_object_store
from ddm_engine.storage.repositories import SqlAlchemyDocumentJobRepository


def test_process_document_extracts_pdf_layout_artifact(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DDM_DATA_ROOT", str(tmp_path))
    monkeypatch.setattr(
        "apps.worker.tasks.DetectionService",
        lambda object_store: StubDetectionService(object_store),
    )
    settings = Settings()
    object_store = create_object_store(settings)
    repository = SqlAlchemyDocumentJobRepository.from_settings(settings)
    job_id = "c" * 32
    original_object_key = f"originals/{job_id}/original.pdf"

    with object_store.open_writer(original_object_key) as output:
        output.write(_make_pdf_bytes("Jane Doe"))

    timestamp = datetime.now(UTC)
    repository.create(
        JobRecord(
            job_id=job_id,
            status=JobStatus.QUEUED,
            original_filename="sample.pdf",
            original_object_key=original_object_key,
            file_type="pdf",
            content_type="application/pdf",
            size_bytes=123,
            redacted_object_key=None,
            failure_reason=None,
            created_at=timestamp,
            updated_at=timestamp,
        )
    )

    result = process_document.run(job_id)

    assert result["status"] == "ready"
    assert result["layout_object_key"] == f"extracted/{job_id}/layout.json"
    assert int(result["page_count"]) == 1
    assert int(result["token_count"]) >= 2
    assert int(result["candidate_count"]) == 0
    assert int(result["decision_count"]) == 0
    assert int(result["region_count"]) == 0
    assert result["redacted_object_key"] == f"redacted/{job_id}/redacted.pdf"

    job = repository.get(job_id)
    assert job.status == JobStatus.READY
    assert job.redacted_object_key == f"redacted/{job_id}/redacted.pdf"

    layout = json.loads(object_store.read_bytes(result["layout_object_key"]))
    assert layout["job_id"] == job_id
    assert layout["pages"][0]["tokens"][0]["text"] == "Jane"

    detections = json.loads(object_store.read_bytes(f"detections/{job_id}/candidates.json"))
    assert detections["job_id"] == job_id

    plan = json.loads(object_store.read_bytes(f"plans/{job_id}/redaction_plan.json"))
    assert plan["job_id"] == job_id
    assert plan["decisions"] == []
    assert plan["regions"] == []

    assert object_store.exists(f"redacted/{job_id}/redacted.pdf")


class StubDetectionService:
    def __init__(self, object_store) -> None:
        self.object_store = object_store

    def detect(self, job) -> DetectionResult:
        with self.object_store.open_writer(f"detections/{job.job_id}/candidates.json") as output:
            output.write(f'{{"job_id":"{job.job_id}","candidates":[]}}'.encode())
        return DetectionResult(job_id=job.job_id, candidates=[])


def _make_pdf_bytes(text: str) -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    try:
        return document.tobytes()
    finally:
        document.close()
