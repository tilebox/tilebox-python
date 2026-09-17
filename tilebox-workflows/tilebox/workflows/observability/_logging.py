"""Lightweight structured logging; independent of exporter and runner initialization."""

import logging
import os
from typing import Any

_WORKFLOW_LOG_ATTRIBUTES = "tilebox_structured_log_attributes"
_LOGGING_NAMESPACE = "tilebox.workflows"


class _NormalizedAttributes(dict[str, Any]):
    """JSON-compatible values already normalized for all handlers on a record."""


def _normalize_attributes(attributes: dict[str, Any]) -> _NormalizedAttributes:
    from tilebox.workflows._serialization import normalize_log_value  # noqa: PLC0415 -- keep imports lightweight

    return _NormalizedAttributes({key: normalize_log_value(value) for key, value in attributes.items()})


def _record_attributes(record: logging.LogRecord) -> _NormalizedAttributes:
    attributes = getattr(record, _WORKFLOW_LOG_ATTRIBUTES, None)
    if not isinstance(attributes, _NormalizedAttributes):
        # Plain stdlib records bypass the facade. Normalize on the first handler,
        # then share the result without modifying the caller's original dictionary.
        attributes = _normalize_attributes(attributes if isinstance(attributes, dict) else _current_span_attributes())
        setattr(record, _WORKFLOW_LOG_ATTRIBUTES, attributes)
    return attributes


def internal_log_level() -> int:
    enabled = os.environ.get("TILEBOX_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}
    return logging.DEBUG if enabled else logging.ERROR


def _current_span_attributes() -> dict[str, str]:
    try:
        from opentelemetry.trace import get_current_span  # noqa: PLC0415
    except ImportError:
        return {}

    span_context = get_current_span().get_span_context()
    if not span_context.is_valid:
        return {}
    return {"trace_id": f"{span_context.trace_id:032x}", "span_id": f"{span_context.span_id:016x}"}


class StructuredLogger:
    """Structured records backed by stdlib logging, with optional current-span attributes."""

    def __init__(self, logger: logging.Logger, attributes: dict[str, Any] | None = None) -> None:
        self._logger = logger
        self._attributes = attributes or {}

    def bind(self, **attributes: Any) -> "StructuredLogger":
        return StructuredLogger(self._logger, self._attributes | attributes)

    def log(self, level: int, message: object, /, *args: Any, **attributes: Any) -> None:
        self._log(level, message, args, attributes, exc_info=False)

    def debug(self, message: object, /, *args: Any, **attributes: Any) -> None:
        self._log(logging.DEBUG, message, args, attributes, exc_info=False)

    def info(self, message: object, /, *args: Any, **attributes: Any) -> None:
        self._log(logging.INFO, message, args, attributes, exc_info=False)

    def warning(self, message: object, /, *args: Any, **attributes: Any) -> None:
        self._log(logging.WARNING, message, args, attributes, exc_info=False)

    def error(self, message: object, /, *args: Any, **attributes: Any) -> None:
        self._log(logging.ERROR, message, args, attributes, exc_info=False)

    def exception(self, message: object, /, *args: Any, **attributes: Any) -> None:
        self._log(logging.ERROR, message, args, attributes, exc_info=True)

    def critical(self, message: object, /, *args: Any, **attributes: Any) -> None:
        self._log(logging.CRITICAL, message, args, attributes, exc_info=False)

    def _log(
        self, level: int, message: object, args: tuple[Any, ...], attributes: dict[str, Any], *, exc_info: bool
    ) -> None:
        if not self._logger.isEnabledFor(level):
            return
        attributes = _normalize_attributes({**self._attributes, **attributes, **_current_span_attributes()})
        self._logger.log(
            level,
            message,
            *args,
            exc_info=exc_info,
            extra={_WORKFLOW_LOG_ATTRIBUTES: attributes},
            stacklevel=3,
        )


root_logger = logging.getLogger(_LOGGING_NAMESPACE)
root_logger.setLevel(logging.DEBUG)
# User task messages emitted through context.logger. Defaults to INFO; configure
# with TILEBOX_LOG_LEVEL, `tilebox runner start --log-level debug`, or
# observability.logging.configure_log_level(logging.DEBUG) in direct Python usage.
task_logger = logging.getLogger(f"{_LOGGING_NAMESPACE}.tasks")
task_logger.setLevel(getattr(logging, os.environ.get("TILEBOX_LOG_LEVEL", "INFO").strip().upper(), logging.INFO))
# SDK/runner diagnostics. Defaults to ERROR; TILEBOX_DEBUG=true enables DEBUG
# (also with the CLI: `TILEBOX_DEBUG=true tilebox runner start`). Direct Python
# callers can override this with observability.logging.configure_log_level(..., tilebox_debug=True).
internal_logger = logging.getLogger(f"{_LOGGING_NAMESPACE}.internal")
internal_logger.setLevel(internal_log_level())
logger = StructuredLogger(internal_logger)
