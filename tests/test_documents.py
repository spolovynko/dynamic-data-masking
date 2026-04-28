import json
from pathlib import Path

import fitz
from fastapi.testclient import TestClient

from apps.api.main import create_app
from apps.api.queue import EnqueuedTask
from ddm_engine.config import Settings
from ddm_engine.extraction.models import BoundingBox, DocumentLayout, LayoutToken, PageLayout
from ddm_engine.storage.jobs import JobStatus
from ddm_engine.storage.object_store import create_object_store
from ddm_engine.storage.repositories import SqlAlchemyDocumentJobRepository


def test_upload_document_creates_job(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DDM_DATA_ROOT", str(tmp_path))
    client = TestClient(create_app())

    response = client.post(
        "/api/documents",
        files={"file": ("sample.txt", b"hello Jane Doe", "text/plain")},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["status"] == "uploaded"
    assert payload["filename"] == "sample.txt"
    assert payload["file_type"] == "txt"
    assert payload["content_type"] == "text/plain"
    assert payload["size_bytes"] == len(b"hello Jane Doe")

    job_id = payload["job_id"]
    object_path = tmp_path / "objects" / "originals" / job_id / "original.txt"
    assert object_path.read_bytes() == b"hello Jane Doe"
    assert (tmp_path / "metadata.sqlite3").exists()


def test_get_job_status(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DDM_DATA_ROOT", str(tmp_path))
    client = TestClient(create_app())
    upload_response = client.post(
        "/api/documents",
        files={"file": ("sample.pdf", b"%PDF-1.7\n", "application/pdf")},
    )
    job_id = upload_response.json()["job_id"]

    response = client.get(f"/api/jobs/{job_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["job_id"] == job_id
    assert payload["status"] == "uploaded"
    assert payload["filename"] == "sample.pdf"
    assert payload["file_type"] == "pdf"


def test_process_job_marks_job_queued_and_returns_task_id(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DDM_DATA_ROOT", str(tmp_path))
    monkeypatch.setattr(
        "apps.api.queue.enqueue_document_processing_job",
        lambda job_id, correlation_id=None: EnqueuedTask(task_id=f"task-{job_id}"),
    )
    client = TestClient(create_app())
    upload_response = client.post(
        "/api/documents",
        files={"file": ("sample.pdf", b"%PDF-1.7\n", "application/pdf")},
    )
    job_id = upload_response.json()["job_id"]

    response = client.post(f"/api/jobs/{job_id}/process")

    assert response.status_code == 200
    payload = response.json()
    assert payload["job_id"] == job_id
    assert payload["status"] == "queued"
    assert payload["task_id"] == f"task-{job_id}"

    status_response = client.get(f"/api/jobs/{job_id}")
    assert status_response.json()["status"] == "queued"


def test_process_job_reverts_status_when_enqueue_fails(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DDM_DATA_ROOT", str(tmp_path))

    def raise_enqueue_error(job_id: str) -> EnqueuedTask:
        raise RuntimeError(f"broker unavailable for {job_id}")

    monkeypatch.setattr("apps.api.queue.enqueue_document_processing_job", raise_enqueue_error)
    client = TestClient(create_app())
    upload_response = client.post(
        "/api/documents",
        files={"file": ("sample.pdf", b"%PDF-1.7\n", "application/pdf")},
    )
    job_id = upload_response.json()["job_id"]

    response = client.post(f"/api/jobs/{job_id}/process")

    assert response.status_code == 503
    assert response.json()["detail"] == "Failed to enqueue background job"

    status_response = client.get(f"/api/jobs/{job_id}")
    assert status_response.json()["status"] == "uploaded"


def test_get_detections_returns_candidates(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DDM_DATA_ROOT", str(tmp_path))
    client = TestClient(create_app())
    upload_response = client.post(
        "/api/documents",
        files={"file": ("sample.pdf", b"%PDF-1.7\n", "application/pdf")},
    )
    job_id = upload_response.json()["job_id"]
    detections_dir = tmp_path / "objects" / "detections" / job_id
    detections_dir.mkdir(parents=True)
    (detections_dir / "candidates.json").write_text(
        json.dumps(
            {
                "job_id": job_id,
                "candidates": [
                    {
                        "candidate_id": "cand-1",
                        "label": "EMAIL_ADDRESS",
                        "text": "jane@example.com",
                        "detector": "regex",
                        "confidence": 0.99,
                        "page_number": 1,
                        "start_char": 8,
                        "end_char": 24,
                        "token_ids": ["p1-t2"],
                        "boxes": [{"x0": 10, "y0": 10, "x1": 80, "y1": 20}],
                        "needs_llm_review": False,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    response = client.get(f"/api/jobs/{job_id}/detections")

    assert response.status_code == 200
    payload = response.json()
    assert payload["job_id"] == job_id
    assert payload["candidate_count"] == 1
    assert payload["candidates"][0]["label"] == "EMAIL_ADDRESS"
    assert payload["candidates"][0]["text"] == "jane@example.com"


def test_get_detections_returns_404_when_not_ready(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DDM_DATA_ROOT", str(tmp_path))
    client = TestClient(create_app())
    upload_response = client.post(
        "/api/documents",
        files={"file": ("sample.pdf", b"%PDF-1.7\n", "application/pdf")},
    )
    job_id = upload_response.json()["job_id"]

    response = client.get(f"/api/jobs/{job_id}/detections")

    assert response.status_code == 404
    assert response.json()["detail"] == "Detections are not available for this job yet"


def test_get_redaction_plan_returns_plan(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DDM_DATA_ROOT", str(tmp_path))
    client = TestClient(create_app())
    upload_response = client.post(
        "/api/documents",
        files={"file": ("sample.pdf", b"%PDF-1.7\n", "application/pdf")},
    )
    job_id = upload_response.json()["job_id"]
    plan_dir = tmp_path / "objects" / "plans" / job_id
    plan_dir.mkdir(parents=True)
    (plan_dir / "redaction_plan.json").write_text(
        json.dumps(
            {
                "job_id": job_id,
                "decisions": [
                    {
                        "decision_id": "decision-1",
                        "status": "mask",
                        "label": "EMAIL_ADDRESS",
                        "text": "jane@example.com",
                        "confidence": 0.99,
                        "page_number": 1,
                        "start_char": 8,
                        "end_char": 24,
                        "token_ids": ["p1-t2"],
                        "boxes": [{"x0": 10, "y0": 20, "x1": 80, "y1": 32}],
                        "detector_names": ["regex"],
                        "source_candidate_ids": ["cand-1"],
                        "reason": "Selected regex detection.",
                    }
                ],
                "regions": [
                    {
                        "region_id": "region-1",
                        "decision_id": "decision-1",
                        "label": "EMAIL_ADDRESS",
                        "page_number": 1,
                        "bbox": {"x0": 8.5, "y0": 18.5, "x1": 81.5, "y1": 33.5},
                        "source_candidate_ids": ["cand-1"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    response = client.get(f"/api/jobs/{job_id}/redaction-plan")

    assert response.status_code == 200
    payload = response.json()
    assert payload["job_id"] == job_id
    assert payload["decision_count"] == 1
    assert payload["region_count"] == 1
    assert payload["decisions"][0]["label"] == "EMAIL_ADDRESS"


def test_get_redaction_plan_returns_404_when_not_ready(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DDM_DATA_ROOT", str(tmp_path))
    client = TestClient(create_app())
    upload_response = client.post(
        "/api/documents",
        files={"file": ("sample.pdf", b"%PDF-1.7\n", "application/pdf")},
    )
    job_id = upload_response.json()["job_id"]

    response = client.get(f"/api/jobs/{job_id}/redaction-plan")

    assert response.status_code == 404
    assert response.json()["detail"] == "Redaction plan is not available for this job yet"


def test_get_extracted_text_returns_text_from_layout(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DDM_DATA_ROOT", str(tmp_path))
    client = TestClient(create_app())
    upload_response = client.post(
        "/api/documents",
        files={"file": ("sample.pdf", b"%PDF-1.7\n", "application/pdf")},
    )
    job_id = upload_response.json()["job_id"]
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
                    _token("p1-t1", "Visible", 10, 10, 40, 20),
                    _token("p1-t2", "jane@example.com", 45, 10, 120, 20),
                ],
            )
        ],
    )
    layout_dir = tmp_path / "objects" / "extracted" / job_id
    layout_dir.mkdir(parents=True)
    (layout_dir / "layout.json").write_text(layout.model_dump_json(), encoding="utf-8")

    response = client.get(f"/api/jobs/{job_id}/text/extracted")

    assert response.status_code == 200
    payload = response.json()
    assert payload["job_id"] == job_id
    assert payload["source"] == "extracted"
    assert payload["pages"][0]["text"] == "Visible jane@example.com"
    assert payload["char_count"] == len("Visible jane@example.com")


def test_get_extracted_text_returns_404_when_not_ready(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DDM_DATA_ROOT", str(tmp_path))
    client = TestClient(create_app())
    upload_response = client.post(
        "/api/documents",
        files={"file": ("sample.pdf", b"%PDF-1.7\n", "application/pdf")},
    )
    job_id = upload_response.json()["job_id"]

    response = client.get(f"/api/jobs/{job_id}/text/extracted")

    assert response.status_code == 404
    assert response.json()["detail"] == "Extracted text is not available for this job yet"


def test_get_redacted_text_returns_text_from_redacted_pdf(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DDM_DATA_ROOT", str(tmp_path))
    client = TestClient(create_app())
    upload_response = client.post(
        "/api/documents",
        files={"file": ("sample.pdf", b"%PDF-1.7\n", "application/pdf")},
    )
    job_id = upload_response.json()["job_id"]
    redacted_key = f"redacted/{job_id}/redacted.pdf"

    settings = Settings()
    object_store = create_object_store(settings)
    with object_store.open_writer(redacted_key) as output:
        output.write(_make_pdf_bytes("Visible public text"))
    repository = SqlAlchemyDocumentJobRepository.from_settings(settings)
    repository.update_redacted_output(job_id, redacted_key, JobStatus.READY)

    response = client.get(f"/api/jobs/{job_id}/text/redacted")

    assert response.status_code == 200
    payload = response.json()
    assert payload["job_id"] == job_id
    assert payload["source"] == "redacted"
    assert "Visible public text" in payload["pages"][0]["text"]


def test_get_redacted_text_returns_404_when_not_ready(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DDM_DATA_ROOT", str(tmp_path))
    client = TestClient(create_app())
    upload_response = client.post(
        "/api/documents",
        files={"file": ("sample.pdf", b"%PDF-1.7\n", "application/pdf")},
    )
    job_id = upload_response.json()["job_id"]

    response = client.get(f"/api/jobs/{job_id}/text/redacted")

    assert response.status_code == 404
    assert response.json()["detail"] == "Redacted text is not available for this job yet"


def test_download_redacted_document_returns_pdf(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DDM_DATA_ROOT", str(tmp_path))
    client = TestClient(create_app())
    upload_response = client.post(
        "/api/documents",
        files={"file": ("sample.pdf", b"%PDF-1.7\n", "application/pdf")},
    )
    job_id = upload_response.json()["job_id"]
    redacted_key = f"redacted/{job_id}/redacted.pdf"

    settings = Settings()
    object_store = create_object_store(settings)
    with object_store.open_writer(redacted_key) as output:
        output.write(b"%PDF-1.7\n%redacted\n")
    repository = SqlAlchemyDocumentJobRepository.from_settings(settings)
    repository.update_redacted_output(job_id, redacted_key, JobStatus.READY)

    response = client.get(f"/api/jobs/{job_id}/download")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content == b"%PDF-1.7\n%redacted\n"


def test_download_redacted_document_returns_404_when_not_ready(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("DDM_DATA_ROOT", str(tmp_path))
    client = TestClient(create_app())
    upload_response = client.post(
        "/api/documents",
        files={"file": ("sample.pdf", b"%PDF-1.7\n", "application/pdf")},
    )
    job_id = upload_response.json()["job_id"]

    response = client.get(f"/api/jobs/{job_id}/download")

    assert response.status_code == 404
    assert response.json()["detail"] == "Redacted document is not available for this job yet"


def test_upload_rejects_unsupported_file_type(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DDM_DATA_ROOT", str(tmp_path))
    client = TestClient(create_app())

    response = client.post(
        "/api/documents",
        files={"file": ("archive.zip", b"not a document", "application/zip")},
    )

    assert response.status_code == 400
    assert ".docx" in response.json()["detail"]
    assert ".pdf" in response.json()["detail"]


def test_upload_rejects_oversized_file(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DDM_DATA_ROOT", str(tmp_path))
    monkeypatch.setenv("DDM_MAX_UPLOAD_BYTES", "4")
    client = TestClient(create_app())

    response = client.post(
        "/api/documents",
        files={"file": ("large.txt", b"12345", "text/plain")},
    )

    assert response.status_code == 413
    assert response.json()["detail"] == "Upload exceeds maximum size of 4 bytes"
    object_root = tmp_path / "objects" / "originals"
    assert not object_root.exists() or not any(object_root.rglob("*"))


def test_get_job_returns_404_for_unknown_job(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DDM_DATA_ROOT", str(tmp_path))
    client = TestClient(create_app())

    response = client.get("/api/jobs/00000000000000000000000000000000")

    assert response.status_code == 404


def _token(token_id: str, text: str, x0: float, y0: float, x1: float, y1: float) -> LayoutToken:
    return LayoutToken(
        token_id=token_id,
        page_number=1,
        text=text,
        bbox=BoundingBox(x0=x0, y0=y0, x1=x1, y1=y1),
    )


def _make_pdf_bytes(text: str) -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    try:
        return document.tobytes()
    finally:
        document.close()
