from ddm_engine.detection.llm_detector import LLMSpecialCategoryDetector
from ddm_engine.detection.text_index import build_page_text_indexes
from ddm_engine.extraction.models import BoundingBox, DocumentLayout, LayoutToken, PageLayout
from ddm_engine.llm.decision_engine import SpecialCategoryDecisionEngine
from ddm_engine.llm.validator import validate_detection_response


def test_validate_detection_response_accepts_special_categories() -> None:
    response = validate_detection_response(
        """
        {
          "findings": [
            {
              "text": "fingerprint scan",
              "label": "BIOMETRIC_DATA",
              "should_mask": true,
              "confidence": 0.91,
              "risk_level": "high",
              "reason": "Biometric identifier."
            }
          ]
        }
        """
    )

    assert response.findings[0].label == "BIOMETRIC_DATA"
    assert response.findings[0].should_mask is True


def test_validate_detection_response_normalizes_empty_reason() -> None:
    response = validate_detection_response(
        """
        {
          "findings": [
            {
              "text": "diabetes",
              "label": "HEALTH_DATA",
              "should_mask": true,
              "confidence": 0.95,
              "risk_level": "high",
              "reason": ""
            }
          ]
        }
        """
    )

    assert response.findings[0].reason == "Model did not provide a reason."


def test_validate_detection_response_accepts_physical_address() -> None:
    response = validate_detection_response(
        """
        {
          "findings": [
            {
              "text": "221B Baker Street, London NW1 6XE",
              "label": "PHYSICAL_ADDRESS",
              "should_mask": true,
              "confidence": 0.94,
              "risk_level": "high",
              "reason": "Specific home address."
            }
          ]
        }
        """
    )

    assert response.findings[0].label == "PHYSICAL_ADDRESS"
    assert response.findings[0].text == "221B Baker Street, London NW1 6XE"


def test_llm_detector_maps_exact_finding_to_tokens() -> None:
    layout = DocumentLayout(
        job_id="job-1",
        source_file_type="pdf",
        pages=[
            PageLayout(
                page_number=1,
                width=612,
                height=792,
                rotation=0,
                tokens=[
                    _token("p1-t1", "Employee", 10, 10, 55, 20),
                    _token("p1-t2", "reported", 60, 10, 100, 20),
                    _token("p1-t3", "fingerprint", 105, 10, 155, 20),
                    _token("p1-t4", "scan", 160, 10, 190, 20),
                ],
            )
        ],
    )
    detector = LLMSpecialCategoryDetector(
        SpecialCategoryDecisionEngine(
            client=FakeLLMClient(
                '{"findings":[{"text":"fingerprint scan","label":"BIOMETRIC_DATA",'
                '"should_mask":true,"confidence":0.93,"risk_level":"high",'
                '"reason":"Biometric identifier."}]}'
            ),
            max_context_chars=1200,
        )
    )

    candidates = detector.detect("job-1", build_page_text_indexes(layout))

    assert len(candidates) == 1
    assert candidates[0].label == "BIOMETRIC_DATA"
    assert candidates[0].text == "fingerprint scan"
    assert candidates[0].token_ids == ["p1-t3", "p1-t4"]


def test_llm_detector_keeps_high_confidence_inconsistent_mask_decision() -> None:
    layout = DocumentLayout(
        job_id="job-1",
        source_file_type="pdf",
        pages=[
            PageLayout(
                page_number=1,
                width=612,
                height=792,
                rotation=0,
                tokens=[
                    _token("p1-t1", "Uses", 10, 10, 35, 20),
                    _token("p1-t2", "fingerprint", 40, 10, 90, 20),
                    _token("p1-t3", "scan", 95, 10, 120, 20),
                    _token("p1-t4", "access", 125, 10, 160, 20),
                ],
            )
        ],
    )
    detector = LLMSpecialCategoryDetector(
        SpecialCategoryDecisionEngine(
            client=FakeLLMClient(
                '{"findings":[{"text":"fingerprint scan access","label":"BIOMETRIC_DATA",'
                '"should_mask":false,"confidence":0.98,"risk_level":"medium",'
                '"reason":"Biometric identifier."}]}'
            ),
            max_context_chars=1200,
        )
    )

    candidates = detector.detect("job-1", build_page_text_indexes(layout))

    assert len(candidates) == 1
    assert candidates[0].label == "BIOMETRIC_DATA"


def test_llm_detector_maps_physical_address_to_tokens() -> None:
    layout = DocumentLayout(
        job_id="job-1",
        source_file_type="pdf",
        pages=[
            PageLayout(
                page_number=1,
                width=612,
                height=792,
                rotation=0,
                tokens=[
                    _token("p1-t1", "Address:", 10, 10, 55, 20),
                    _token("p1-t2", "221B", 60, 10, 88, 20),
                    _token("p1-t3", "Baker", 93, 10, 125, 20),
                    _token("p1-t4", "Street,", 130, 10, 170, 20),
                    _token("p1-t5", "London", 175, 10, 215, 20),
                    _token("p1-t6", "NW1", 220, 10, 245, 20),
                    _token("p1-t7", "6XE", 250, 10, 275, 20),
                ],
            )
        ],
    )
    detector = LLMSpecialCategoryDetector(
        SpecialCategoryDecisionEngine(
            client=FakeLLMClient(
                '{"findings":[{"text":"221B Baker Street, London NW1 6XE",'
                '"label":"PHYSICAL_ADDRESS","should_mask":true,"confidence":0.94,'
                '"risk_level":"high","reason":"Specific home address."}]}'
            ),
            max_context_chars=1200,
        )
    )

    candidates = detector.detect("job-1", build_page_text_indexes(layout))

    assert len(candidates) == 1
    assert candidates[0].label == "PHYSICAL_ADDRESS"
    assert candidates[0].token_ids == ["p1-t2", "p1-t3", "p1-t4", "p1-t5", "p1-t6", "p1-t7"]


def test_decision_engine_retries_invalid_llm_output() -> None:
    engine = SpecialCategoryDecisionEngine(
        client=SequencedFakeLLMClient(
            [
                "not-json",
                '{"findings":[{"text":"fingerprint scan","label":"BIOMETRIC_DATA",'
                '"should_mask":true,"confidence":0.93,"risk_level":"high",'
                '"reason":"Biometric identifier."}]}',
            ]
        ),
        max_context_chars=1200,
    )

    response = engine.detect("The access log references a fingerprint scan.")

    assert len(response.findings) == 1
    assert response.findings[0].label == "BIOMETRIC_DATA"


def test_decision_engine_returns_empty_response_after_invalid_outputs() -> None:
    engine = SpecialCategoryDecisionEngine(
        client=SequencedFakeLLMClient(["not-json", "still-not-json"]),
        max_context_chars=1200,
    )

    response = engine.detect("The access log references a fingerprint scan.")

    assert response.findings == []


class FakeLLMClient:
    def __init__(self, output: str) -> None:
        self.output = output

    def generate_json(self, prompt: str) -> str:
        return self.output


class SequencedFakeLLMClient:
    def __init__(self, outputs: list[str]) -> None:
        self.outputs = outputs
        self.index = 0

    def generate_json(self, prompt: str) -> str:
        output = self.outputs[self.index]
        self.index += 1
        return output


def _token(token_id: str, text: str, x0: float, y0: float, x1: float, y1: float) -> LayoutToken:
    return LayoutToken(
        token_id=token_id,
        page_number=1,
        text=text,
        bbox=BoundingBox(x0=x0, y0=y0, x1=x1, y1=y1),
    )
