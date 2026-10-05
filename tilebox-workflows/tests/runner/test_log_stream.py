import logging
import sys
import threading
import time

import pytest
from opentelemetry.proto.logs.v1.logs_pb2 import LogRecord, SeverityNumber

from tilebox.workflows.observability._log_stream import _LogQueue, _OTLPQueueHandler


def _record(message: str) -> LogRecord:
    record = LogRecord()
    record.body.string_value = message
    return record


def test_full_sealed_queue_drains_without_sentinel() -> None:
    records = _LogQueue(capacity=2)
    records.submit(_record("one"))
    records.submit(_record("two"))
    records.seal()

    assert [record.body.string_value for record in records.subscribe()] == ["one", "two"]
    assert list(records.subscribe()) == []


def test_overflow_notice_is_emitted_without_another_submission() -> None:
    records = _LogQueue(capacity=1)
    records.submit(_record("kept"))
    records.submit(_record("lost-one"))
    records.submit(_record("lost-two"))
    records.seal()

    assert [record.body.string_value for record in records.subscribe()] == [
        "kept",
        "Dropped 2 local log records",
    ]


def test_cancelled_subscription_reconnects_and_does_not_consume_full_queue() -> None:
    records = _LogQueue(capacity=1)
    records.submit(_record("buffered"))
    assert list(records.subscribe(lambda: False)) == []
    records.seal()
    assert [record.body.string_value for record in records.subscribe()] == ["buffered"]


def test_overflow_notice_precedes_new_records_after_delivery_resumes() -> None:
    records = _LogQueue(capacity=2)
    records.submit(_record("first"))
    records.submit(_record("second"))
    records.submit(_record("lost"))
    subscriber = records.subscribe()
    assert next(subscriber).body.string_value == "first"
    assert next(subscriber).body.string_value == "second"
    records.submit(_record("after loss"))
    records.seal()
    assert [record.body.string_value for record in subscriber] == [
        "Dropped 1 local log records",
        "after loss",
    ]


def test_concurrent_subscription_is_rejected() -> None:
    records = _LogQueue()
    subscribed = threading.Event()
    release = threading.Event()

    def active() -> bool:
        subscribed.set()
        return not release.is_set()

    subscriber = threading.Thread(target=lambda: list(records.subscribe(active)))
    subscriber.start()
    assert subscribed.wait(timeout=1)
    with pytest.raises(RuntimeError, match="already connected"):
        next(records.subscribe())
    release.set()
    subscriber.join(timeout=1)
    assert not subscriber.is_alive()


def test_wait_empty_is_bounded_without_consumer() -> None:
    records = _LogQueue()
    records.submit(_record("buffered"))
    started = time.monotonic()
    assert not records.wait_empty(timeout=0.02)
    assert time.monotonic() - started < 0.5


def test_oversize_record_is_replaced_by_drop_notice() -> None:
    records = _LogQueue(max_record_size=32)
    records.submit(_record("x" * 100))
    records.seal()
    assert [record.body.string_value for record in records.subscribe()] == ["Dropped 1 local log records"]


@pytest.mark.parametrize(
    ("value", "field"),
    [
        (True, "bool_value"),
        (False, "bool_value"),
        (0, "int_value"),
        (2**63 - 1, "int_value"),
        (-(2**63 - 1), "int_value"),
        (2**63, "string_value"),
        (-(2**63), "string_value"),
        (-(2**63) - 1, "string_value"),
        (2**80, "string_value"),
        (-(2**80), "string_value"),
    ],
)
def test_handler_preserves_integer_boundaries(value: int, field: str) -> None:
    records = _LogQueue()
    handler = _OTLPQueueHandler(records)
    record = logging.LogRecord("test", logging.INFO, __file__, 1, "integer attribute", (), None)
    record.tilebox_structured_log_attributes = {"value": value, "nested": {"items": [value]}}
    handler.emit(record)
    handler.emit(logging.LogRecord("test", logging.INFO, __file__, 1, "next record", (), None))
    records.seal()

    first, second = records.subscribe()
    assert first.body.string_value == "integer attribute"
    assert second.body.string_value == "next record"
    attributes = {item.key: item.value for item in first.attributes}
    nested = attributes["nested"].kvlist_value.values[0]
    assert nested.key == "items"
    for result in (attributes["value"], nested.value.array_value.values[0]):
        assert result.WhichOneof("value") == field
        assert getattr(result, field) == (str(value) if field == "string_value" else value)


def test_handler_preserves_structured_attributes_exception_trace_and_level() -> None:
    records = _LogQueue()
    handler = _OTLPQueueHandler(records)

    def fail() -> None:
        raise ValueError("bad value")

    try:
        fail()
    except ValueError:
        record = logging.LogRecord("test", logging.WARNING, __file__, 1, "failed", (), exc_info=sys.exc_info())
        record.tilebox_structured_log_attributes = {
            "items": [1, "two"],
            "mapping": {"nested": True},
            "missing": None,
            "trace_id": "01" * 16,
            "span_id": "02" * 8,
        }
        handler.emit(record)
    records.seal()
    [result] = records.subscribe()
    attributes = {item.key: item.value for item in result.attributes}
    assert result.severity_number == SeverityNumber.SEVERITY_NUMBER_WARN
    assert result.severity_text == "WARN"
    assert result.trace_id == b"\x01" * 16
    assert result.span_id == b"\x02" * 8
    assert [item.int_value or item.string_value for item in attributes["items"].array_value.values] == [1, "two"]
    assert attributes["mapping"].kvlist_value.values[0].value.bool_value
    assert attributes["missing"].WhichOneof("value") is None
    assert attributes["exception.type"].string_value == "ValueError"
    assert "ValueError: bad value" in attributes["exception.stacktrace"].string_value
