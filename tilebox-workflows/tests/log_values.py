from tilebox.workflows._otel.opentelemetry.proto.common.v1.common_pb import AnyValue


def string_value(value: AnyValue | None) -> str:
    """Assert that a native OTEL value contains the string variant and return it."""
    assert value is not None
    assert value.value is not None
    assert value.value.field == "string_value"
    return value.value.value
