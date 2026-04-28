import json
from datetime import UTC, datetime

import fitz

from apps.worker.tasks import process_document
from ddm_engine.config import Settings
from ddm_engine.storage.jobs import JobRecord, JobStatus
from ddm_engine.storage.object_store import create_object_store
from ddm_engine.storage.repositories import SqlAlchemyDocumentJobRepository


def test_process_document_extracts_pdf_layout_artifact(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DDM_DATA_ROOT", str(tmp_path))
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

    assert result["status"] == "detecting"
    assert result["layout_object_key"] == f"extracted/{job_id}/layout.json"
    assert int(result["page_count"]) == 1
    assert int(result["token_count"]) >= 2

    job = repository.get(job_id)
    assert job.status == JobStatus.DETECTING

    layout = json.loads(object_store.read_bytes(result["layout_object_key"]))
    assert layout["job_id"] == job_id
    assert layout["pages"][0]["tokens"][0]["text"] == "Jane"


def _make_pdf_bytes(text: str) -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    try:
        return document.tobytes()
    finally:
        document.close()
