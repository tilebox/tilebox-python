"""Public enum ingestion and xarray reads through both client implementations."""

from dataclasses import replace
from datetime import UTC, datetime
from inspect import isawaitable
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pandas as pd
import pytest
from protobuf.wkt.google.protobuf.descriptor_pb import (
    DescriptorProto,
    Edition,
    EnumDescriptorProto,
    EnumValueDescriptorProto,
    FieldDescriptorProto,
    FileDescriptorProto,
    FileDescriptorSet,
)
from protobuf.wkt.google.protobuf.timestamp_pb import Timestamp

from _tilebox.proto.tilebox.v1.id_pb import ID
from tilebox.datasets import DatasetClient, field
from tilebox.datasets.aio import DatasetClient as AsyncDatasetClient
from tilebox.datasets.data.datasets import AnnotatedType, Dataset, FieldAnnotation
from tilebox.datasets.message_pool import get_message_type
from tilebox.datasets.v1 import core_pb, data_access_pb, data_ingestion_pb
from tilebox.query.pagination import Pagination


@pytest.fixture
def enum_schema() -> AnnotatedType:
    schema = FileDescriptorProto(
        name="enum.proto",
        package="tests.enums",
        syntax="editions",
        edition=Edition.EDITION_2023,
        dependency=["google/protobuf/timestamp.proto"],
        enum_type=[
            EnumDescriptorProto(
                name="Level",
                value=[
                    EnumValueDescriptorProto(name=name, number=number)
                    for name, number in [("ZERO", 0), ("FIRST", 17), ("SECOND", 4), ("THIRD", 9)]
                ],
            )
        ],
        message_type=[
            DescriptorProto(name="Unrelated"),
            DescriptorProto(
                name="Row",
                field=[
                    FieldDescriptorProto(
                        name="time",
                        number=20,
                        type=FieldDescriptorProto.Type.MESSAGE,
                        type_name=".google.protobuf.Timestamp",
                        label=FieldDescriptorProto.Label.OPTIONAL,
                    ),
                    FieldDescriptorProto(
                        name="level",
                        number=7,
                        type=FieldDescriptorProto.Type.ENUM,
                        type_name=".tests.enums.Level",
                        label=FieldDescriptorProto.Label.OPTIONAL,
                    ),
                    FieldDescriptorProto(
                        name="scene",
                        number=11,
                        type=FieldDescriptorProto.Type.STRING,
                        label=FieldDescriptorProto.Label.OPTIONAL,
                    ),
                ],
            ),
        ],
    )
    return AnnotatedType(
        FileDescriptorSet(file=[FileDescriptorProto(name="other.proto", package="other"), schema]),
        "type.googleapis.com/tests.enums.Row",
        [FieldAnnotation("", ""), FieldAnnotation("", "", enum_values=["L1", "L2-SP", "雪"]), FieldAnnotation("", "")],
    )


def _client(schema: AnnotatedType, asynchronous: bool = False) -> tuple[Any, Any]:
    service = AsyncMock() if asynchronous else MagicMock()
    service.get_collection_by_name.return_value = core_pb.CollectionInfo(
        collection=core_pb.Collection(id=ID(uuid=UUID(int=2).bytes), name="test"),
    )
    connection = MagicMock()
    connection.client.return_value = service
    dataset = Dataset(UUID(int=1), UUID(int=0), schema, "test", "Test", "", "", "")
    client_type = AsyncDatasetClient if asynchronous else DatasetClient
    return client_type(connection, dataset), service


async def _resolve(value: Any) -> Any:
    return await value if isawaitable(value) else value


@pytest.fixture
def repeated_enum_schema(enum_schema: AnnotatedType) -> AnnotatedType:
    enum_schema.descriptor_set.file[1].message_type[1].field[1].label = FieldDescriptorProto.Label.REPEATED
    return enum_schema


@pytest.mark.asyncio
@pytest.mark.parametrize("asynchronous", [False, True])
async def test_repeated_enum_ingestion_and_reads(repeated_enum_schema: AnnotatedType, asynchronous: bool) -> None:
    client, service = _client(repeated_enum_schema, asynchronous)
    collection = await _resolve(client.collection("test"))
    row = get_message_type(repeated_enum_schema)
    time = Timestamp.from_seconds(1)
    raw = [row(time=time), row(time=time), row(time=time, level=[4, 17, 4]), row(time=time, level=[9])]
    stored = [row(time=time), row(time=time), row(time=time, level=[4, 17]), row(time=time, level=[9])]
    captured = []

    def ingest(request: data_ingestion_pb.IngestRequest) -> data_ingestion_pb.IngestResponse:
        captured[:] = request.values  # noqa: PD011 -- protobuf field
        return data_ingestion_pb.IngestResponse()

    service.ingest.side_effect = ingest
    records = [
        {"time": datetime.fromtimestamp(1, UTC), "level": values}
        for values in [None, [], ["L2-SP", "L1", "L2-SP"], ["雪"]]
    ]
    columns = {"time": [record["time"] for record in records], "level": [record["level"] for record in records]}
    for data in (records, columns, pd.DataFrame(records)):
        await _resolve(collection.ingest(data))
        assert [row.from_binary(value) for value in captured] == raw

    # Deduplication belongs to the backend. Read its normalized payload, including a first page with only empty lists.
    def query_page(request: data_access_pb.QueryRequest) -> data_access_pb.QueryResultPage:
        if request.page is not None and request.page.starting_after is not None:
            return data_access_pb.QueryResultPage(data=core_pb.RepeatedAny(value=[m.to_binary() for m in stored[2:]]))
        return data_access_pb.QueryResultPage(
            data=core_pb.RepeatedAny(value=[m.to_binary() for m in stored[:2]]),
            next_page=Pagination(starting_after=UUID(int=2)).to_message(),
        )

    service.query.side_effect = query_page
    service.query_by_id.return_value = core_pb.Any(value=stored[2].to_binary())
    for target in (client, collection):
        result = await _resolve(target.query(temporal_extent=("1970", "1971")))
        assert result.level.dims == ("time",)
        assert result.level.shape == (4,)
        assert result.level.dtype == object
        assert result.level.to_numpy().tolist() == [[], [], ["L2-SP", "L1"], ["雪"]]
        assert all(isinstance(value, list) for value in result.level.to_numpy())
        assert "n_level" not in result.dims
        assert (await _resolve(target.find(UUID(int=3)))).level.item() == ["L2-SP", "L1"]
        assert "level" not in await _resolve(target.query(temporal_extent=("1970", "1971"), skip_data=True))
    await _resolve(collection.ingest(result))
    assert [row.from_binary(value) for value in captured] == stored
    result.level[0].item().append("L1")
    assert result.level[1].item() == []
    service.query.side_effect = None
    service.query.return_value = data_access_pb.QueryResultPage(data=core_pb.RepeatedAny(value=[stored[0].to_binary()]))
    empty = await _resolve(collection.query(temporal_extent=("1970", "1971")))
    assert empty.level.dims == ("time",)
    assert empty.level.item() == []
    for value in ("L1", [0], [17], ["FIRST"], ["L1"] * 100 + ["unknown"]):
        with pytest.raises((TypeError, ValueError), match="Field 'level'"):
            await _resolve(collection.ingest([{"time": "2026-01-01", "level": value}]))
    await _resolve(collection.ingest([{"time": "2026-01-01", "level": ["L1"] * 101}]))
    message: Any = row.from_binary(captured[0])
    assert list(message.level) == [17] * 101
    for number in (0, 99):
        service.query_by_id.return_value = core_pb.Any(value=bytes([0x3A, 2, 4, number]))
        with pytest.raises(ValueError, match="Invalid enum value"):
            await _resolve(client.find(UUID(int=3)))


@pytest.mark.asyncio
@pytest.mark.parametrize("asynchronous", [False, True])
async def test_public_enum_ingestion_and_reads(enum_schema: AnnotatedType, asynchronous: bool) -> None:
    client, service = _client(enum_schema, asynchronous)
    collection = await _resolve(client.collection("test"))
    row = get_message_type(enum_schema)
    time = Timestamp.from_seconds(1)
    expected = [row(time=time, level=17), row(time=time, level=4), row(time=time, level=9), row(time=time)]
    captured = []

    def ingest(request: data_ingestion_pb.IngestRequest) -> data_ingestion_pb.IngestResponse:
        captured[:] = request.values  # noqa: PD011 -- protobuf field
        return data_ingestion_pb.IngestResponse(datapoint_ids=[ID(uuid=UUID(int=i).bytes) for i in range(1, 5)])

    service.ingest.side_effect = ingest
    records = [{"time": datetime.fromtimestamp(1, UTC), "level": value} for value in ["L1", "L2-SP", "雪", None]]
    columns = {"time": [record["time"] for record in records], "level": [record["level"] for record in records]}
    for data in (records, columns, pd.DataFrame(records)):
        ids = await _resolve(collection.ingest(data))
        assert ids == [UUID(int=i) for i in range(1, 5)]
        assert [row.from_binary(value) for value in captured] == expected

    # Separate server fixtures from the encoder under test; include an absent field.
    wire = [message.to_binary() for message in expected]

    def query_page(request: data_access_pb.QueryRequest) -> data_access_pb.QueryResultPage:
        if request.page is not None and request.page.starting_after is not None:
            return data_access_pb.QueryResultPage(data=core_pb.RepeatedAny(value=wire[2:]))
        return data_access_pb.QueryResultPage(
            data=core_pb.RepeatedAny(value=wire[:2]),
            next_page=Pagination(starting_after=UUID(int=2)).to_message(),
        )

    service.query.side_effect = query_page
    service.query_by_id.return_value = core_pb.Any(value=wire[1])
    for target in (client, collection):
        result = await _resolve(target.query(temporal_extent=("1970", "1971")))
        assert result.level.dtype == object
        assert result.level[:3].to_numpy().tolist() == ["L1", "L2-SP", "雪"]
        assert result.level.isnull().to_numpy().tolist() == [False, False, False, True]  # noqa: PD003 -- xarray API
        assert result.where(result.level.isin(["L2-SP", "雪"]), drop=True).level.to_numpy().tolist() == ["L2-SP", "雪"]
        assert (await _resolve(target.find(UUID(int=3)))).level.item() == "L2-SP"
        assert "level" not in await _resolve(target.query(temporal_extent=("1970", "1971"), skip_data=True))
        assert "level" not in await _resolve(target.find(UUID(int=3), skip_data=True))
    await _resolve(collection.ingest(result))
    assert [row.from_binary(value) for value in captured] == expected

    # The SDK sends public strings unchanged; membership and operator checks belong to the server.
    def query(request: data_access_pb.QueryRequest) -> data_access_pb.QueryResultPage:
        assert request.filters is not None
        comparison = request.filters.expressions[0].comparison
        assert comparison is not None
        assert comparison.value is not None
        assert comparison.value.string_value == "L2-SP"
        return data_access_pb.QueryResultPage(data=core_pb.RepeatedAny(value=[wire[1]]))

    service.query.side_effect = query
    result = await _resolve(client.query(temporal_extent=("1970", "1971"), filter=field("level") == "L2-SP"))
    assert result.level.to_numpy().tolist() == ["L2-SP"]


@pytest.mark.asyncio
@pytest.mark.parametrize("asynchronous", [False, True])
async def test_invalid_public_enum_values(enum_schema: AnnotatedType, asynchronous: bool) -> None:
    client, service = _client(enum_schema, asynchronous)
    collection = await _resolve(client.collection("test"))
    for value in (0, 17, 4.0, True, "FIRST", "l1", "unknown", ""):
        with pytest.raises((ValueError, TypeError), match="Record 0: Field 'level'"):
            await _resolve(collection.ingest([{"time": "2026-01-01", "level": value}]))

    for number in (0, 99):
        # Field 7, wire type 0. Check explicit zero independently of message constructors.
        wire = bytes([0x38, number])
        service.query_by_id.return_value = core_pb.Any(value=wire)
        service.query.return_value = data_access_pb.QueryResultPage(data=core_pb.RepeatedAny(value=[wire]))
        with pytest.raises(ValueError, match="Invalid enum value"):
            await _resolve(client.find(UUID(int=3)))
        if asynchronous:
            with pytest.raises(ExceptionGroup) as error:
                await _resolve(client.query(temporal_extent=("2026", "2027")))
            assert len(error.value.exceptions) == 1
            assert isinstance(error.value.exceptions[0], ValueError)
            assert "Invalid enum value" in str(error.value.exceptions[0])
        else:
            with pytest.raises(ValueError, match="Invalid enum value"):
                await _resolve(client.query(temporal_extent=("2026", "2027")))


def test_enum_schema_isolation_and_append(enum_schema: AnnotatedType) -> None:
    client, service = _client(enum_schema)
    service.query_by_id.return_value = core_pb.Any(value=b"\x38\x04")
    renamed = replace(
        enum_schema,
        field_annotations=[
            FieldAnnotation("", ""),
            FieldAnnotation("", "", enum_values=["a", "b", "c"]),
            FieldAnnotation("", ""),
        ],
    )
    other, other_service = _client(renamed)
    other_service.query_by_id.return_value = core_pb.Any(value=b"\x38\x04")
    assert other.find(UUID(int=3)).level.item() == "b"
    assert client.find(UUID(int=3)).level.item() == "L2-SP"

    updated = AnnotatedType.from_message(enum_schema.to_message())
    updated.descriptor_set.file[1].enum_type[0].value.append(EnumValueDescriptorProto(name="FOURTH", number=31))
    updated.field_annotations[1].enum_values.append("L3")
    refreshed, refreshed_service = _client(updated)
    refreshed_service.query_by_id.return_value = core_pb.Any(value=b"\x38\x1f")
    assert refreshed.find(UUID(int=3)).level.item() == "L3"
    refreshed_service.query_by_id.return_value = core_pb.Any(value=b"\x38\x04")
    assert refreshed.find(UUID(int=3)).level.item() == "L2-SP"
    assert client.find(UUID(int=3)).level.item() == "L2-SP"


@pytest.mark.parametrize(
    "problem", ["alignment", "short", "long", "empty", "duplicate", "wrong_type", "wrong_repeated_type"]
)
def test_invalid_enum_annotations(enum_schema: AnnotatedType, problem: str) -> None:
    if problem == "alignment":
        enum_schema.field_annotations.pop(0)
    elif problem == "short":
        enum_schema.field_annotations[1].enum_values.pop()
    elif problem == "long":
        enum_schema.field_annotations[1].enum_values.append("L3")
    elif problem == "empty":
        enum_schema.field_annotations[1].enum_values[0] = ""
    elif problem == "duplicate":
        enum_schema.field_annotations[1].enum_values[0] = "L2-SP"
    elif problem == "wrong_type":
        enum_schema.field_annotations[0], enum_schema.field_annotations[1] = (
            enum_schema.field_annotations[1],
            enum_schema.field_annotations[0],
        )
    else:
        descriptor = enum_schema.descriptor_set.file[1].message_type[1].field[1]
        descriptor.label = FieldDescriptorProto.Label.REPEATED
        descriptor.type = FieldDescriptorProto.Type.STRING
        descriptor.type_name = ""
    with pytest.raises((ValueError, TypeError), match=r"annotation|enum_values"):
        _client(enum_schema)
