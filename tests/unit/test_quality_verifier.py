import fitz

from ddm_engine.extraction.models import BoundingBox
from ddm_engine.planning.models import (
    RedactionDecision,
    RedactionDecisionStatus,
    RedactionPlan,
    RedactionRegion,
)
from ddm_engine.quality.models import VerificationStatus
from ddm_engine.quality.verifier import RedactionVerifier


def test_redaction_verifier_detects_extractable_sensitive_text() -> None:
    plan = _plan("jane@example.com")
    report = RedactionVerifier().verify(
        job_id="job-1",
        redacted_pdf_bytes=_make_pdf_bytes("Visible jane@example.com"),
        plan=plan,
    )

    assert report.status == VerificationStatus.FAILED
    assert report.leak_count == 1
    assert report.leaks[0].label == "EMAIL_ADDRESS"


def test_redaction_verifier_passes_when_sensitive_text_is_removed() -> None:
    plan = _plan("jane@example.com")
    report = RedactionVerifier().verify(
        job_id="job-1",
        redacted_pdf_bytes=_make_pdf_bytes("Visible [redacted]"),
        plan=plan,
    )

    assert report.status == VerificationStatus.PASSED
    assert report.leaks == []


def _plan(text: str) -> RedactionPlan:
    box = BoundingBox(x0=10, y0=10, x1=100, y1=20)
    decision = RedactionDecision(
        decision_id="decision-1",
        status=RedactionDecisionStatus.MASK,
        label="EMAIL_ADDRESS",
        text=text,
        confidence=0.99,
        page_number=1,
        start_char=8,
        end_char=24,
        token_ids=["p1-t2"],
        boxes=[box],
        detector_names=["regex"],
        source_candidate_ids=["cand-1"],
        reason="Selected regex detection.",
    )
    return RedactionPlan(
        job_id="job-1",
        decisions=[decision],
        regions=[
            RedactionRegion(
                region_id="region-1",
                decision_id=decision.decision_id,
                label=decision.label,
                page_number=1,
                bbox=box,
                source_candidate_ids=["cand-1"],
            )
        ],
    )


def _make_pdf_bytes(text: str) -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    try:
        return document.tobytes()
    finally:
        document.close()
