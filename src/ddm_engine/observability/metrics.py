from prometheus_client import Counter, Gauge, Histogram

API_REQUESTS_TOTAL = Counter(
    "ddm_api_requests_total",
    "Total API requests.",
    ["method", "route", "status_code"],
)
API_REQUEST_DURATION_SECONDS = Histogram(
    "ddm_api_request_duration_seconds",
    "API request duration in seconds.",
    ["method", "route"],
)
API_REQUESTS_IN_PROGRESS = Gauge(
    "ddm_api_requests_in_progress",
    "API requests currently in progress.",
    ["method"],
)

UPLOADED_DOCUMENTS_TOTAL = Counter(
    "ddm_uploaded_documents_total",
    "Uploaded documents.",
    ["file_type"],
)
JOBS_ENQUEUED_TOTAL = Counter(
    "ddm_jobs_enqueued_total",
    "Jobs enqueued for background processing.",
)
JOB_DURATION_SECONDS = Histogram(
    "ddm_job_duration_seconds",
    "Background job duration in seconds.",
    ["final_status"],
)
JOB_FAILURES_TOTAL = Counter(
    "ddm_job_failures_total",
    "Background job failures.",
    ["reason"],
)
OCR_DURATION_SECONDS = Histogram(
    "ddm_ocr_duration_seconds",
    "OCR extraction duration in seconds.",
    ["source_type", "outcome"],
)
OCR_TOKENS_TOTAL = Counter(
    "ddm_ocr_tokens_total",
    "Tokens extracted by OCR.",
    ["source_type"],
)
ENTITIES_DETECTED_TOTAL = Counter(
    "ddm_entities_detected_total",
    "Detected sensitive entities.",
    ["label", "detector"],
)
LLM_CALLS_TOTAL = Counter(
    "ddm_llm_calls_total",
    "LLM calls.",
    ["provider", "model", "outcome"],
)
LLM_LATENCY_SECONDS = Histogram(
    "ddm_llm_latency_seconds",
    "LLM request latency in seconds.",
    ["provider", "model"],
)
LLM_JSON_VALIDATION_FAILURES_TOTAL = Counter(
    "ddm_llm_json_validation_failures_total",
    "Invalid structured JSON responses from the LLM.",
)
REDACTIONS_APPLIED_TOTAL = Counter(
    "ddm_redactions_applied_total",
    "Redaction boxes applied to documents.",
    ["label"],
)
REDACTION_VERIFICATION_TOTAL = Counter(
    "ddm_redaction_verification_total",
    "Redaction verification outcomes.",
    ["outcome"],
)
SENSITIVE_TEXT_LEAKAGE_TOTAL = Counter(
    "ddm_sensitive_text_leakage_total",
    "Sensitive text leakage detected after redaction.",
    ["label"],
)
HUMAN_OVERRIDES_TOTAL = Counter(
    "ddm_human_overrides_total",
    "Human detection review overrides.",
    ["action"],
)
