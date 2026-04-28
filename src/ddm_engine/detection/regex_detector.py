from __future__ import annotations

import re
from dataclasses import dataclass

from ddm_engine.detection.models import CandidateEntity, DetectorName
from ddm_engine.detection.text_index import PageTextIndex, boxes_for_tokens

PHONE_OVERLAP_PROTECTED_LABELS = {"CREDIT_CARD", "IBAN_CODE"}


@dataclass(frozen=True)
class RegexPattern:
    label: str
    pattern: re.Pattern[str]
    confidence: float


class RegexDetector:
    def __init__(self) -> None:
        self.patterns = [
            RegexPattern(
                label="EMAIL_ADDRESS",
                pattern=re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
                confidence=0.99,
            ),
            RegexPattern(
                label="IBAN_CODE",
                pattern=re.compile(r"\b[A-Z]{2}\d{2}(?: ?[A-Z0-9]){11,30}\b", re.IGNORECASE),
                confidence=0.95,
            ),
            RegexPattern(
                label="CREDIT_CARD",
                pattern=re.compile(r"\b(?:\d[ -]*?){13,19}\b"),
                confidence=0.85,
            ),
            RegexPattern(
                label="PHONE_NUMBER",
                pattern=re.compile(r"\b(?:\+?\d{1,3}[\s.-]?)?(?:\(?\d{2,4}\)?[\s.-]?){2,5}\d{2,4}\b"),
                confidence=0.75,
            ),
            RegexPattern(
                label="SECRET",
                pattern=re.compile(
                    r"\b(?:api[_-]?key|secret|token|bearer)\s*[:=]\s*[A-Za-z0-9._\-]{8,}\b",
                    re.IGNORECASE,
                ),
                confidence=0.9,
            ),
        ]

    def detect(self, job_id: str, indexes: list[PageTextIndex]) -> list[CandidateEntity]:
        candidates: list[CandidateEntity] = []
        for page_index in indexes:
            for regex_pattern in self.patterns:
                for match in regex_pattern.pattern.finditer(page_index.text):
                    if regex_pattern.label == "PHONE_NUMBER" and _overlaps_protected_candidate(
                        candidates,
                        page_index.page_number,
                        match.start(),
                        match.end(),
                    ):
                        continue
                    tokens = page_index.tokens_for_span(match.start(), match.end())
                    if not tokens:
                        continue
                    candidates.append(
                        CandidateEntity(
                            candidate_id=(
                                f"regex-{job_id}-{page_index.page_number}-"
                                f"{match.start()}-{match.end()}-{regex_pattern.label}"
                            ),
                            label=regex_pattern.label,
                            text=match.group(0),
                            detector=DetectorName.REGEX,
                            confidence=regex_pattern.confidence,
                            page_number=page_index.page_number,
                            start_char=match.start(),
                            end_char=match.end(),
                            token_ids=[token.token_id for token in tokens],
                            boxes=boxes_for_tokens(tokens),
                            needs_llm_review=False,
                        )
                    )
        return candidates


def _overlaps_protected_candidate(
    candidates: list[CandidateEntity],
    page_number: int,
    start: int,
    end: int,
) -> bool:
    for candidate in candidates:
        if candidate.page_number != page_number:
            continue
        if candidate.label not in PHONE_OVERLAP_PROTECTED_LABELS:
            continue
        if start < candidate.end_char and end > candidate.start_char:
            return True
    return False
