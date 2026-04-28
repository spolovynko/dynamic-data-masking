from ddm_engine.config import Settings

SPECIAL_CATEGORY_CUES = (
    "address",
    "street",
    "st.",
    "avenue",
    "road",
    "postcode",
    "zip",
    "religion",
    "religious",
    "church",
    "mosque",
    "synagogue",
    "muslim",
    "jewish",
    "catholic",
    "political",
    "party",
    "vote",
    "union",
    "trade union",
    "diagnosis",
    "medical",
    "health",
    "therapy",
    "hiv",
    "diabetes",
    "race",
    "ethnic",
    "nationality",
    "national origin",
    "criminal",
    "arrest",
    "conviction",
    "fingerprint",
    "biometric",
    "retina",
    "sexual orientation",
)


def llm_special_category_detection_enabled(settings: Settings) -> bool:
    return settings.llm_enabled and settings.llm_provider == "ollama"


def should_scan_text_window(text: str) -> bool:
    lowered = text.casefold()
    return any(cue in lowered for cue in SPECIAL_CATEGORY_CUES)
