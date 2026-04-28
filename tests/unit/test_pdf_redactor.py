from datetime import UTC, datetime

import fitz

from ddm_engine.extraction.models import BoundingBox
from ddm_engine.planning.models import (
    RedactionDecision,
    RedactionDecisionStatus,
    RedactionPlan,
    RedactionRegion,
)
from ddm_engine.rendering.pdf_redactor import PDFRedactionService
from ddm_engine.storage.jobs import JobRecord, JobStatus
from ddm_engine.storage.object_store import LocalObjectStore


def test_pdf_redactor_removes_selectable_text(tmp_path) -> None:
    store = LocalObjectStore(tmp_path)
    job_id = "f" * 32
    original_key = f"originals/{job_id}/original.pdf"
    source_pdf = _make_pdf_bytes("Visible public text. Secret: jane@example.com")
    redaction_box = _find_text_box(source_pdf, "jane@example.com")

    with store.open_writer(original_key) as output:
        output.write(source_pdf)
    with store.open_writer(f"plans/{job_id}/redaction_plan.json") as output:
        output.write(_plan(job_id, redaction_box).model_dump_json().encode("utf-8"))

    redacted_key = PDFRedactionService(store).redact(_job(job_id, original_key))

    redacted_pdf = fitz.open(stream=store.read_bytes(redacted_key), filetype="pdf")
    try:
        text = "\n".join(page.get_text() for page in redacted_pdf)
    finally:
        redacted_pdf.close()

    assert "jane@example.com" not in text
    assert "Visible public text" in text


def test_pdf_redactor_converts_image_to_redacted_pdf(tmp_path) -> None:
    store = LocalObjectStore(tmp_path)
    job_id = "1" * 32
    original_key = f"originals/{job_id}/original.png"
    image_bytes = _make_png_bytes()
    box = BoundingBox(x0=20, y0=20, x1=120, y1=60)

    with store.open_writer(original_key) as output:
        output.write(image_bytes)
    with store.open_writer(f"plans/{job_id}/redaction_plan.json") as output:
        output.write(_plan(job_id, box).model_dump_json().encode("utf-8"))

    redacted_key = PDFRedactionService(store).redact(_job(job_id, original_key, file_type="png"))

    redacted_pdf = fitz.open(stream=store.read_bytes(redacted_key), filetype="pdf")
    try:
        assert redacted_pdf.page_count == 1
    finally:
        redacted_pdf.close()


def _make_pdf_bytes(text: str) -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    try:
        return document.tobytes()
    finally:
        document.close()


def _make_png_bytes() -> bytes:
    document = fitz.open()
    page = document.new_page(width=200, height=100)
    page.insert_text((20, 50), "jane@example.com")
    try:
        return page.get_pixmap().tobytes("png")
    finally:
        document.close()


def _find_text_box(pdf_bytes: bytes, text: str) -> BoundingBox:
    document = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        matches = document[0].search_for(text)
        assert matches
        rect = matches[0]
        return BoundingBox(x0=rect.x0, y0=rect.y0, x1=rect.x1, y1=rect.y1)
    finally:
        document.close()


def _plan(job_id: str, box: BoundingBox) -> RedactionPlan:
    decision = RedactionDecision(
        decision_id="decision-1",
        status=RedactionDecisionStatus.MASK,
        label="EMAIL_ADDRESS",
        text="jane@example.com",
        confidence=0.99,
        page_number=1,
        start_char=28,
        end_char=44,
        token_ids=["p1-t4"],
        boxes=[box],
        detector_names=["regex"],
        source_candidate_ids=["candidate-1"],
        reason="Selected regex detection.",
    )
    region = RedactionRegion(
        region_id="region-1",
        decision_id=decision.decision_id,
        label=decision.label,
        page_number=1,
        bbox=box,
        source_candidate_ids=decision.source_candidate_ids,
    )
    return RedactionPlan(job_id=job_id, decisions=[decision], regions=[region])


def _job(job_id: str, original_key: str, file_type: str = "pdf") -> JobRecord:
    now = datetime.now(UTC)
    return JobRecord(
        job_id=job_id,
        status=JobStatus.REDACTING,
        original_filename=f"sample.{file_type}",
        original_object_key=original_key,
        file_type=file_type,
        content_type=f"application/{file_type}",
        size_bytes=100,
        redacted_object_key=None,
        failure_reason=None,
        created_at=now,
        updated_at=now,
    )
