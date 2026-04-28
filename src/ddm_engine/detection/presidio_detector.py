from __future__ import annotations

from functools import cached_property

from presidio_analyzer import AnalyzerEngine
from presidio_analyzer.nlp_engine import NlpEngineProvider

from ddm_engine.detection.models import CandidateEntity, DetectorName
from ddm_engine.detection.text_index import PageTextIndex, boxes_for_tokens

HIGH_CONFIDENCE_ENTITIES = {
    "CREDIT_CARD",
    "EMAIL_ADDRESS",
    "IBAN_CODE",
    "IP_ADDRESS",
    "PHONE_NUMBER",
    "URL",
    "US_SSN",
}


class PresidioDetector:
    def __init__(self, language: str = "en", entities: tuple[str, ...] = ("PERSON",)) -> None:
        self.language = language
        self.entities = entities

    @cached_property
    def analyzer(self) -> AnalyzerEngine:
        configuration = {
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": self.language, "model_name": "en_core_web_sm"}],
        }
        provider = NlpEngineProvider(nlp_configuration=configuration)
        return AnalyzerEngine(
            nlp_engine=provider.create_engine(),
            supported_languages=[self.language],
        )

    def detect(self, job_id: str, indexes: list[PageTextIndex]) -> list[CandidateEntity]:
        candidates: list[CandidateEntity] = []
        for page_index in indexes:
            results = self.analyzer.analyze(
                text=page_index.text,
                language=self.language,
                entities=list(self.entities) if self.entities else None,
            )
            for result in results:
                tokens = page_index.tokens_for_span(result.start, result.end)
                if not tokens:
                    continue

                text = page_index.text[result.start : result.end]
                needs_llm_review = (
                    result.entity_type not in HIGH_CONFIDENCE_ENTITIES or result.score < 0.85
                )
                candidates.append(
                    CandidateEntity(
                        candidate_id=(
                            f"presidio-{job_id}-{page_index.page_number}-"
                            f"{result.start}-{result.end}-{result.entity_type}"
                        ),
                        label=result.entity_type,
                        text=text,
                        detector=DetectorName.PRESIDIO,
                        confidence=result.score,
                        page_number=page_index.page_number,
                        start_char=result.start,
                        end_char=result.end,
                        token_ids=[token.token_id for token in tokens],
                        boxes=boxes_for_tokens(tokens),
                        needs_llm_review=needs_llm_review,
                    )
                )
        return candidates
