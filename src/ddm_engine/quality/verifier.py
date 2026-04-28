from __future__ import annotations

import hashlib
import re

import fitz

from ddm_engine.planning.models import RedactionDecisionStatus, RedactionPlan
from ddm_engine.quality.models import VerificationLeak, VerificationReport, VerificationStatus


class RedactionVerificationError(Exception):
    """Raised when a redacted document cannot be verified."""


class RedactionVerifier:
    def verify(
        self,
        job_id: str,
        redacted_pdf_bytes: bytes,
        plan: RedactionPlan,
    ) -> VerificationReport:
        try:
            document = fitz.open(stream=redacted_pdf_bytes, filetype="pdf")
        except Exception as exc:
            raise RedactionVerificationError("Failed to open redacted PDF") from exc

        try:
            page_text = {page.number + 1: _normalize_text(page.get_text()) for page in document}
        finally:
            document.close()

        leaks: list[VerificationLeak] = []
        checked_decisions = [
            decision
            for decision in plan.decisions
            if decision.status == RedactionDecisionStatus.MASK
        ]
        for decision in checked_decisions:
            if len(decision.text.strip()) < 4:
                continue
            normalized_value = _normalize_text(decision.text)
            if normalized_value and normalized_value in page_text.get(decision.page_number, ""):
                leaks.append(
                    VerificationLeak(
                        decision_id=decision.decision_id,
                        label=decision.label,
                        page_number=decision.page_number,
                        text_hash=hashlib.sha256(decision.text.encode()).hexdigest(),
                    )
                )

        return VerificationReport(
            job_id=job_id,
            status=VerificationStatus.FAILED if leaks else VerificationStatus.PASSED,
            checked_decision_count=len(checked_decisions),
            checked_region_count=len(plan.regions),
            leaks=leaks,
        )


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()
