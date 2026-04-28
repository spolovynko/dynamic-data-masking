from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    service_name: str = Field(default="dynamic-data-masking", validation_alias="DDM_SERVICE_NAME")
    app_name: str = Field(default="Dynamic Data Masking", validation_alias="DDM_APP_NAME")
    app_version: str = Field(default="0.1.0", validation_alias="DDM_APP_VERSION")
    environment: str = Field(default="local", validation_alias="DDM_ENVIRONMENT")

    api_host: str = Field(default="127.0.0.1", validation_alias="DDM_API_HOST")
    api_port: int = Field(default=8000, validation_alias="DDM_API_PORT")
    api_reload: bool = Field(default=True, validation_alias="DDM_API_RELOAD")
    api_prefix: str = Field(default="/api", validation_alias="DDM_API_PREFIX")

    data_root: Path = Field(default=Path("data"), validation_alias="DDM_DATA_ROOT")
    max_upload_bytes: int = Field(
        default=25 * 1024 * 1024,
        validation_alias="DDM_MAX_UPLOAD_BYTES",
    )
    database_url: str | None = Field(default=None, validation_alias="DDM_DATABASE_URL")
    object_store_backend: Literal["local"] = Field(
        default="local",
        validation_alias="DDM_OBJECT_STORE_BACKEND",
    )
    object_store_root: Path | None = Field(default=None, validation_alias="DDM_OBJECT_STORE_ROOT")
    queue_broker_url: str = Field(
        default="redis://localhost:6379/0",
        validation_alias="DDM_QUEUE_BROKER_URL",
    )
    queue_result_backend: str = Field(
        default="redis://localhost:6379/1",
        validation_alias="DDM_QUEUE_RESULT_BACKEND",
    )
    queue_name: str = Field(default="ddm", validation_alias="DDM_QUEUE_NAME")
    celery_task_always_eager: bool = Field(
        default=False,
        validation_alias="DDM_CELERY_TASK_ALWAYS_EAGER",
    )
    worker_pool: str = Field(default="solo", validation_alias="DDM_WORKER_POOL")
    worker_log_level: str = Field(default="INFO", validation_alias="DDM_WORKER_LOG_LEVEL")
    worker_metrics_port: int = Field(default=9101, validation_alias="DDM_WORKER_METRICS_PORT")
    ocr_enabled: bool = Field(default=True, validation_alias="DDM_OCR_ENABLED")
    ocr_language: str = Field(default="eng", validation_alias="DDM_OCR_LANGUAGE")
    ocr_dpi: int = Field(default=200, validation_alias="DDM_OCR_DPI")
    ocr_min_native_tokens: int = Field(default=1, validation_alias="DDM_OCR_MIN_NATIVE_TOKENS")
    presidio_enabled: bool = Field(default=False, validation_alias="DDM_PRESIDIO_ENABLED")
    presidio_entities: str = Field(default="PERSON", validation_alias="DDM_PRESIDIO_ENTITIES")
    llm_enabled: bool = Field(default=False, validation_alias="DDM_LLM_ENABLED")
    llm_provider: Literal["ollama"] = Field(default="ollama", validation_alias="DDM_LLM_PROVIDER")
    ollama_base_url: str = Field(
        default="http://127.0.0.1:11434",
        validation_alias="DDM_OLLAMA_BASE_URL",
    )
    ollama_model: str = Field(default="qwen2.5:3b", validation_alias="DDM_OLLAMA_MODEL")
    llm_temperature: float = Field(default=0.0, validation_alias="DDM_LLM_TEMPERATURE")
    llm_max_context_chars: int = Field(
        default=1200,
        validation_alias="DDM_LLM_MAX_CONTEXT_CHARS",
    )
    llm_timeout_seconds: int = Field(default=120, validation_alias="DDM_LLM_TIMEOUT_SECONDS")
    log_level: str = Field(default="INFO", validation_alias="DDM_LOG_LEVEL")

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return f"sqlite:///{self.data_root / 'metadata.sqlite3'}"

    @property
    def resolved_object_store_root(self) -> Path:
        if self.object_store_root is not None:
            return self.object_store_root
        return self.data_root / "objects"

    @property
    def resolved_presidio_entities(self) -> tuple[str, ...]:
        return tuple(
            entity.strip().upper() for entity in self.presidio_entities.split(",") if entity.strip()
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
