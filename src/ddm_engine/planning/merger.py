from __future__ import annotations

from ddm_engine.detection.models import CandidateEntity, DetectorName
from ddm_engine.llm.schemas import SensitiveCategory
from ddm_engine.planning.models import RedactionDecision, RedactionDecisionStatus

DETERMINISTIC_LABEL_PRIORITY = {
    "EMAIL_ADDRESS": 100,
    "CREDIT_CARD": 100,
    "IBAN_CODE": 100,
    "PHONE_NUMBER": 95,
    "US_SSN": 100,
    "IP_ADDRESS": 90,
    "SECRET": 100,  # nosec B105
}
SPECIAL_CATEGORY_LABELS = {category.value for category in SensitiveCategory}
GENERIC_LABEL_PRIORITY = {
    "PERSON": 80,
    "LOCATION": 70,
    "NRP": 75,
    "ORGANIZATION": 60,
    "DATE_TIME": 45,
    "URL": 35,
}


class DetectionMerger:
    def merge(self, job_id: str, candidates: list[CandidateEntity]) -> list[RedactionDecision]:
        decisions: list[RedactionDecision] = []
        for group_index, group in enumerate(_group_overlapping_candidates(candidates), start=1):
            selected = _select_candidate(group)
            detector_names = sorted({candidate.detector.value for candidate in group})
            source_candidate_ids = sorted(candidate.candidate_id for candidate in group)
            group_confidence = max(candidate.confidence for candidate in group)

            decisions.append(
                RedactionDecision(
                    decision_id=f"decision-{job_id}-{group_index}",
                    status=RedactionDecisionStatus.MASK,
                    label=selected.label,
                    text=selected.text,
                    confidence=group_confidence,
                    page_number=selected.page_number,
                    start_char=selected.start_char,
                    end_char=selected.end_char,
                    token_ids=selected.token_ids,
                    boxes=selected.boxes,
                    detector_names=detector_names,
                    source_candidate_ids=source_candidate_ids,
                    reason=_decision_reason(group, selected),
                )
            )
        return decisions


def _group_overlapping_candidates(
    candidates: list[CandidateEntity],
) -> list[list[CandidateEntity]]:
    ordered = sorted(
        candidates,
        key=lambda item: (item.page_number, item.start_char, item.end_char),
    )
    groups: list[list[CandidateEntity]] = []
    current_group: list[CandidateEntity] = []
    current_page: int | None = None
    current_end = -1

    for candidate in ordered:
        if (
            current_group
            and candidate.page_number == current_page
            and candidate.start_char < current_end
        ):
            current_group.append(candidate)
            current_end = max(current_end, candidate.end_char)
            continue

        if current_group:
            groups.append(current_group)
        current_group = [candidate]
        current_page = candidate.page_number
        current_end = candidate.end_char

    if current_group:
        groups.append(current_group)
    return groups


def _select_candidate(candidates: list[CandidateEntity]) -> CandidateEntity:
    return max(candidates, key=_candidate_rank)


def _candidate_rank(candidate: CandidateEntity) -> tuple[int, float, int]:
    label_priority = _label_priority(candidate.label)
    detector_priority = _detector_priority(candidate.detector)
    length = candidate.end_char - candidate.start_char
    return (label_priority + detector_priority, candidate.confidence, length)


def _label_priority(label: str) -> int:
    if label in DETERMINISTIC_LABEL_PRIORITY:
        return DETERMINISTIC_LABEL_PRIORITY[label]
    if label in SPECIAL_CATEGORY_LABELS:
        return 90
    return GENERIC_LABEL_PRIORITY.get(label, 50)


def _detector_priority(detector: DetectorName) -> int:
    if detector == DetectorName.REGEX:
        return 10
    if detector == DetectorName.LLM:
        return 8
    return 0


def _decision_reason(group: list[CandidateEntity], selected: CandidateEntity) -> str:
    if len(group) == 1:
        return f"Selected {selected.detector.value} detection."
    labels = ", ".join(sorted({candidate.label for candidate in group}))
    detectors = ", ".join(sorted({candidate.detector.value for candidate in group}))
    return (
        f"Merged overlapping detections from {detectors}; selected {selected.label} over {labels}."
    )
