from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
correlation_id_var: ContextVar[str | None] = ContextVar("correlation_id", default=None)


@dataclass(frozen=True)
class ObservabilityContext:
    request_id: str | None
    correlation_id: str | None


def set_observability_context(
    request_id: str | None,
    correlation_id: str | None,
) -> tuple[object, object]:
    request_token = request_id_var.set(request_id)
    correlation_token = correlation_id_var.set(correlation_id)
    return request_token, correlation_token


def reset_observability_context(tokens: tuple[object, object]) -> None:
    request_id_var.reset(tokens[0])
    correlation_id_var.reset(tokens[1])


def get_observability_context() -> ObservabilityContext:
    return ObservabilityContext(
        request_id=request_id_var.get(),
        correlation_id=correlation_id_var.get(),
    )
