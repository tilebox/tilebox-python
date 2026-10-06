"""Bounded OTLP log streaming for CLI-managed workflow runtimes."""

import logging
import os
import threading
import time
import traceback
from collections import deque
from collections.abc import Callable, Iterator
from typing import Any

from opentelemetry.instrumentation.log_utils import std_to_otel
from opentelemetry.proto.common.v1.common_pb2 import AnyValue, ArrayValue, KeyValue, KeyValueList
from opentelemetry.proto.logs.v1.logs_pb2 import LogRecord, SeverityNumber
from opentelemetry.semconv.attributes import exception_attributes

from tilebox.workflows.observability._logging import _record_attributes

_MAX_RECORD_SIZE = 1024 * 1024
_MANAGED_RUNTIME = bool(os.environ.get("TILEBOX_RUNTIME_DIR") and os.environ.get("TILEBOX_RUNTIME_TOKEN"))


def _any_value(value: Any) -> AnyValue:  # noqa: PLR0911 -- each protobuf union arm is clearest explicitly
    """Convert an already-normalized JSON value to OTLP."""
    if value is None:
        return AnyValue()
    if isinstance(value, bool):
        return AnyValue(bool_value=value)
    if isinstance(value, int):
        if abs(value) > 2**63 - 1:
            return AnyValue(string_value=str(value))
        return AnyValue(int_value=value)
    if isinstance(value, float):
        return AnyValue(double_value=value)
    if isinstance(value, dict):
        return AnyValue(
            kvlist_value=KeyValueList(values=[KeyValue(key=key, value=_any_value(item)) for key, item in value.items()])
        )
    if isinstance(value, list):
        return AnyValue(array_value=ArrayValue(values=[_any_value(item) for item in value]))
    return AnyValue(string_value=value)


class _LogQueue:
    """Non-blocking bounded queue with explicit sealed-and-empty termination."""

    def __init__(self, capacity: int = 256, max_record_size: int = _MAX_RECORD_SIZE) -> None:
        self._capacity = capacity
        self._max_record_size = max_record_size
        self._records: deque[LogRecord] = deque()
        self._condition = threading.Condition()
        self._subscriber = False
        self._sealed = False
        self._dropped = 0

    def submit(self, record: LogRecord) -> None:
        with self._condition:
            if self._sealed:
                return
            if record.ByteSize() > self._max_record_size or len(self._records) >= self._capacity:
                self._dropped += 1
                self._condition.notify_all()
                return
            if self._dropped:
                self._records.append(_drop_record(self._dropped))
                self._dropped = 0
            if len(self._records) >= self._capacity:
                self._dropped += 1
                self._condition.notify_all()
                return
            self._records.append(record)
            self._condition.notify_all()

    def subscribe(self, active: Callable[[], bool] = lambda: True) -> Iterator[LogRecord]:
        with self._condition:
            if self._subscriber:
                raise RuntimeError("A log subscriber is already connected")
            self._subscriber = True
        try:
            while active():
                with self._condition:
                    if self._records:
                        record = self._records.popleft()
                        self._condition.notify_all()
                    elif self._dropped:
                        record = _drop_record(self._dropped)
                        self._dropped = 0
                        self._condition.notify_all()
                    elif self._sealed:
                        return
                    else:
                        self._condition.wait(timeout=0.1)
                        continue
                yield record
        finally:
            with self._condition:
                self._subscriber = False
                self._condition.notify_all()

    def seal(self) -> None:
        with self._condition:
            self._sealed = True
            self._condition.notify_all()

    def wait_empty(self, timeout: float) -> bool:
        deadline = time.monotonic() + timeout
        with self._condition:
            while self._records or self._dropped:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self._condition.wait(timeout=remaining)
            return True


def _drop_record(count: int) -> LogRecord:
    return LogRecord(
        time_unix_nano=time.time_ns(),
        severity_number=_severity_number(logging.WARNING),
        severity_text="WARN",
        body=AnyValue(string_value=f"Dropped {count} local log records"),
    )


class _OTLPQueueHandler(logging.Handler):
    def __init__(self, records: _LogQueue) -> None:
        super().__init__(logging.NOTSET)
        self._records = records

    def emit(self, record: logging.LogRecord) -> None:
        try:
            attributes = dict(_record_attributes(record))
            trace_id = _hex_id(attributes.pop("trace_id", ""), 16)
            span_id = _hex_id(attributes.pop("span_id", ""), 8)
            if record.exc_info:
                exctype, value, tb = record.exc_info
                if exctype is not None:
                    attributes[exception_attributes.EXCEPTION_TYPE] = exctype.__name__
                if value is not None:
                    attributes[exception_attributes.EXCEPTION_MESSAGE] = str(value)
                if tb is not None:
                    attributes[exception_attributes.EXCEPTION_STACKTRACE] = "".join(
                        traceback.format_exception(*record.exc_info)
                    )
            self._records.submit(
                LogRecord(
                    time_unix_nano=int(record.created * 1e9),
                    severity_number=_severity_number(record.levelno),
                    severity_text={"WARNING": "WARN", "CRITICAL": "FATAL"}.get(record.levelname, record.levelname),
                    body=_any_value(record.getMessage()),
                    attributes=[KeyValue(key=str(key), value=_any_value(value)) for key, value in attributes.items()],
                    trace_id=trace_id,
                    span_id=span_id,
                )
            )
        except Exception:  # noqa: BLE001 -- logging must never break workflow execution
            self.handleError(record)


def _hex_id(value: Any, size: int) -> bytes:
    try:
        result = bytes.fromhex(value) if isinstance(value, str) else b""
    except ValueError:
        return b""
    return result if len(result) == size else b""


def _severity_number(level: int) -> SeverityNumber.ValueType:
    return SeverityNumber.Value(f"SEVERITY_NUMBER_{std_to_otel(level).name}")


managed_log_queue = _LogQueue() if _MANAGED_RUNTIME else None
