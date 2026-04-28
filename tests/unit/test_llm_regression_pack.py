import json
from pathlib import Path

from ddm_engine.llm.router import should_scan_text_window
from ddm_engine.llm.schemas import SensitiveCategory


def test_sensitive_category_fixture_labels_are_supported() -> None:
    fixture_path = Path(__file__).parents[1] / "fixtures" / "llm_sensitive_cases.json"
    cases = json.loads(fixture_path.read_text(encoding="utf-8"))
    supported_labels = {category.value for category in SensitiveCategory}

    assert cases
    for case in cases:
        assert case["expected_label"] in supported_labels
        assert should_scan_text_window(case["text"])
