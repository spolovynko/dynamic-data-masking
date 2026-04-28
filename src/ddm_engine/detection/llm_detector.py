from __future__ import annotations

from ddm_engine.detection.models import CandidateEntity, DetectorName
from ddm_engine.detection.text_index import PageTextIndex, boxes_for_tokens
from ddm_engine.llm.decision_engine import SpecialCategoryDecisionEngine
from ddm_engine.llm.router import should_scan_text_window


class LLMSpecialCategoryDetector:
    def __init__(self, decision_engine: SpecialCategoryDecisionEngine) -> None:
        self.decision_engine = decision_engine

    def detect(self, job_id: str, indexes: list[PageTextIndex]) -> list[CandidateEntity]:
        candidates: list[CandidateEntity] = []
        for page_index in indexes:
            if not should_scan_text_window(page_index.text):
                continue
            response = self.decision_engine.detect(page_index.text)
            for finding_index, finding in enumerate(response.findings, start=1):
                should_keep = finding.should_mask or (
                    finding.risk_level in {"medium", "high"} and finding.confidence >= 0.9
                )
                if not should_keep:
                    continue

                span = page_index.find_text_span(finding.text)
                if span is None:
                    continue
                start, end = span
                tokens = page_index.tokens_for_span(start, end)
                if not tokens:
                    continue

                candidates.append(
                    CandidateEntity(
                        candidate_id=(
                            f"llm-{job_id}-{page_index.page_number}-{start}-{end}-{finding_index}"
                        ),
                        label=finding.label.value,
                        text=finding.text,
                        detector=DetectorName.LLM,
                        confidence=finding.confidence,
                        page_number=page_index.page_number,
                        start_char=start,
                        end_char=end,
                        token_ids=[token.token_id for token in tokens],
                        boxes=boxes_for_tokens(tokens),
                        needs_llm_review=False,
                    )
                )
        return candidates
