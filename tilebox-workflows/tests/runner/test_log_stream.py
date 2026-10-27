import asyncio
import logging
import sys
import time

import pytest
from protobuf import Oneof
from tests.log_values import string_value

from tilebox.workflows._otel.opentelemetry.proto.common.v1.common_pb import AnyValue, ArrayValue, KeyValue, KeyValueList
from tilebox.workflows._otel.opentelemetry.proto.logs.v1.logs_pb import LogRecord, SeverityNumber
from tilebox.workflows.observability._log_stream import _LogQueue, _OTLPQueueHandler


def _record(message: str) -> LogRecord:
    return LogRecord(body=AnyValue(value=Oneof("string_value", message)))


@pytest.mark.asyncio
async def test_full_sealed_queue_drains_without_sentinel() -> None:
    records = _LogQueue(capacity=2)
    records.submit(_record("one"))
    records.submit(_record("two"))
    records.seal()

    assert [string_value(record.body) async for record in records.subscribe_async()] == ["one", "two"]
    assert [record async for record in records.subscribe_async()] == []


@pytest.mark.asyncio
async def test_overflow_notice_is_emitted_without_another_submission() -> None:
    records = _LogQueue(capacity=1)
    records.submit(_record("kept"))
    records.submit(_record("lost-one"))
    records.submit(_record("lost-two"))
    records.seal()

    assert [string_value(record.body) async for record in records.subscribe_async()] == [
        "kept",
        "Dropped 2 local log records",
    ]


@pytest.mark.asyncio
async def test_overflow_notice_precedes_new_records_after_delivery_resumes() -> None:
    records = _LogQueue(capacity=2)
    records.submit(_record("first"))
    records.submit(_record("second"))
    records.submit(_record("lost"))
    subscriber = records.subscribe_async()
    assert string_value((await anext(subscriber)).body) == "first"
    assert string_value((await anext(subscriber)).body) == "second"
    records.submit(_record("after loss"))
    records.seal()
    assert [string_value(record.body) async for record in subscriber] == [
        "Dropped 1 local log records",
        "after loss",
    ]


def test_wait_empty_is_bounded_without_consumer() -> None:
    records = _LogQueue()
    records.submit(_record("buffered"))
    started = time.monotonic()
    assert not records.wait_empty(timeout=0.02)
    assert time.monotonic() - started < 0.5


@pytest.mark.asyncio
async def test_oversize_record_is_replaced_by_drop_notice() -> None:
    records = _LogQueue(max_record_size=32)
    records.submit(_record("x" * 100))
    records.seal()
    assert [string_value(record.body) async for record in records.subscribe_async()] == ["Dropped 1 local log records"]


@pytest.mark.asyncio
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
async def test_handler_preserves_integer_boundaries(value: int, field: str) -> None:
    records = _LogQueue()
    handler = _OTLPQueueHandler(records)
    record = logging.LogRecord("test", logging.INFO, __file__, 1, "integer attribute", (), None)
    record.tilebox_structured_log_attributes = {"value": value, "nested": {"items": [value]}}
    handler.emit(record)
    handler.emit(logging.LogRecord("test", logging.INFO, __file__, 1, "next record", (), None))
    records.seal()

    first, second = [record async for record in records.subscribe_async()]
    assert string_value(first.body) == "integer attribute"
    assert string_value(second.body) == "next record"
    attributes = {item.key: item.value for item in first.attributes}
    if field == "string_value":
        expected = AnyValue(value=Oneof("string_value", str(value)))
    elif field == "bool_value":
        assert isinstance(value, bool)
        expected = AnyValue(value=Oneof("bool_value", value))
    else:
        assert field == "int_value"
        expected = AnyValue(value=Oneof("int_value", value))
    assert attributes["value"] == expected
    assert attributes["nested"] == AnyValue(
        value=Oneof(
            "kvlist_value",
            KeyValueList(
                values=[
                    KeyValue(key="items", value=AnyValue(value=Oneof("array_value", ArrayValue(values=[expected]))))
                ]
            ),
        )
    )


@pytest.mark.asyncio
async def test_handler_preserves_structured_attributes_exception_trace_and_level() -> None:
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
    [result] = [record async for record in records.subscribe_async()]
    attributes = {item.key: item.value for item in result.attributes}
    assert result.severity_number == SeverityNumber.WARN
    assert result.severity_text == "WARN"
    assert result.trace_id == b"\x01" * 16
    assert result.span_id == b"\x02" * 8
    assert attributes["items"] == AnyValue(
        value=Oneof(
            "array_value",
            ArrayValue(values=[AnyValue(value=Oneof("int_value", 1)), AnyValue(value=Oneof("string_value", "two"))]),
        )
    )
    assert attributes["mapping"] == AnyValue(
        value=Oneof(
            "kvlist_value",
            KeyValueList(values=[KeyValue(key="nested", value=AnyValue(value=Oneof("bool_value", True)))]),
        )
    )
    assert attributes["missing"] == AnyValue()
    assert string_value(attributes["exception.type"]) == "ValueError"
    assert "ValueError: bad value" in string_value(attributes["exception.stacktrace"])


@pytest.mark.asyncio
async def test_async_subscription_cancellation_releases_single_subscriber() -> None:
    """Cancel an idle async subscriber without consuming future records or retaining a thread."""
    records = _LogQueue(capacity=1)
    subscriber = records.subscribe_async()
    pending = asyncio.create_task(anext(subscriber))
    await asyncio.sleep(0.02)
    with pytest.raises(RuntimeError, match="already connected"):
        await anext(records.subscribe_async())
    pending.cancel()
    with pytest.raises(asyncio.CancelledError):
        await pending
    records.submit(_record("after cancellation"))
    records.submit(_record("overflow"))
    records.seal()
    assert [string_value(record.body) async for record in records.subscribe_async()] == [
        "after cancellation",
        "Dropped 1 local log records",
    ]
