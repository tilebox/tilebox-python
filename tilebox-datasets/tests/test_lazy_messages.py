"""Lazy query fields and their ingestion wire contract."""

from inspect import isawaitable
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pandas as pd
import pytest
import xarray as xr
from hypothesis import given
from hypothesis import strategies as st
from protobuf.wkt.google.protobuf.descriptor_pb import (
    DescriptorProto,
    FieldDescriptorProto,
    FileDescriptorProto,
    FileDescriptorSet,
)
from protobuf.wkt.google.protobuf.timestamp_pb import Timestamp

from _tilebox.proto.tilebox.v1.id_pb import ID
from tilebox.datasets import DatasetClient, LazyMessage
from tilebox.datasets.aio import DatasetClient as AsyncDatasetClient
from tilebox.datasets.data.datasets import AnnotatedType, Dataset
from tilebox.datasets.message_pool import get_message_type
from tilebox.datasets.protobuf_conversion.field_types import encoded_message_field_types
from tilebox.datasets.protobuf_conversion.protobuf_xarray import MessageToXarrayConverter
from tilebox.datasets.protobuf_conversion.to_protobuf import to_messages
from tilebox.datasets.schema import Assets, Authentication, Links, Storage
from tilebox.datasets.stac.v1.asset_pb import Asset
from tilebox.datasets.stac.v1.core_pb import Link
from tilebox.datasets.v1 import core_pb, data_access_pb, data_ingestion_pb


def _schema() -> AnnotatedType:
    fields = [
        FieldDescriptorProto(
            name="time",
            number=1,
            type=FieldDescriptorProto.Type.MESSAGE,
            type_name=".google.protobuf.Timestamp",
            label=FieldDescriptorProto.Label.OPTIONAL,
        ),
        FieldDescriptorProto(
            name="cloud_cover",
            number=2,
            type=FieldDescriptorProto.Type.DOUBLE,
            label=FieldDescriptorProto.Label.OPTIONAL,
        ),
    ]
    for number, (name, message_type) in enumerate(
        [
            ("catalog", Assets),
            ("links", Links),
            ("storage", Storage),
            ("authentication", Authentication),
            ("related", Assets),
        ],
        start=3,
    ):
        fields.append(
            FieldDescriptorProto(
                name=name,
                number=number,
                type=FieldDescriptorProto.Type.MESSAGE,
                type_name=f".{message_type.desc().type_name}",
                label=FieldDescriptorProto.Label.REPEATED if name == "related" else FieldDescriptorProto.Label.OPTIONAL,
            )
        )
    file = FileDescriptorProto(
        name="lazy.proto",
        package="tests.lazy",
        syntax="proto2",
        dependency=[
            "google/protobuf/timestamp.proto",
            "datasets/stac/v1/asset.proto",
            "datasets/stac/v1/core.proto",
            "datasets/stac/v1/storage.proto",
            "datasets/stac/v1/authentication.proto",
        ],
        message_type=[DescriptorProto(name="Row", field=fields)],
    )
    return AnnotatedType(FileDescriptorSet(file=[file]), "tests.lazy.Row", [])


async def _resolve(value: Any) -> Any:
    return await value if isawaitable(value) else value


@pytest.mark.asyncio
@pytest.mark.parametrize("asynchronous", [False, True])
async def test_lazy_query_find_and_ingestion(asynchronous: bool) -> None:  # noqa: PLR0915
    schema = _schema()
    row = get_message_type(schema)
    unknown = b"\xa0\x06\x07"  # Unknown field 100, varint 7.
    assets = Assets.from_binary(Assets(assets=[Asset(key="red")]).to_binary() + unknown)
    first = row(
        time=Timestamp.from_seconds(1),
        cloud_cover=12.5,
        catalog=assets,
        links=Links(links=[Link(href="https://example.com")]),
        storage=Storage(),
        authentication=Authentication(),
        related=[Assets(), Assets(assets=[Asset(key="blue")])],
    )
    raw = [
        first,
        row(time=Timestamp.from_seconds(2), cloud_cover=0.0, catalog=Assets()),
        row(time=Timestamp.from_seconds(3), cloud_cover=7.5),
        row.from_binary(first.to_binary()),
    ]
    service = AsyncMock() if asynchronous else MagicMock()
    service.get_collection_by_name.return_value = core_pb.CollectionInfo(
        collection=core_pb.Collection(id=ID(uuid=UUID(int=2).bytes), name="test"),
    )
    service.query.return_value = data_access_pb.QueryResultPage(
        data=core_pb.RepeatedAny(value=[m.to_binary() for m in raw])
    )
    service.query_by_id.return_value = core_pb.Any(value=first.to_binary())
    captured = []

    def ingest(request: data_ingestion_pb.IngestRequest) -> data_ingestion_pb.IngestResponse:
        captured[:] = request.values  # noqa: PD011 -- protobuf field
        return data_ingestion_pb.IngestResponse()

    service.ingest.side_effect = ingest
    connection = MagicMock()
    connection.client.return_value = service
    client_type = AsyncDatasetClient if asynchronous else DatasetClient
    client = client_type(connection, Dataset(UUID(int=1), UUID(int=0), schema, "test", "Test", "", "", ""))
    collection = await _resolve(client.collection("test"))
    for target in (client, collection):
        result = await _resolve(target.query(temporal_extent=("1970", "1971")))
        assert result.cloud_cover.to_numpy().tolist() == [12.5, 0.0, 7.5, 12.5]
        assert result.catalog.dims == ("time",)
        assert result.related.shape == (4, 2)
        assert result.catalog[2].item() is None
        assert result.catalog[1].item().to_binary() == b""  # Present empty != missing.
        assert result.related[0, 0].item().to_binary() == b""
        lazy = result.catalog[0].item()
        assert isinstance(lazy, LazyMessage)
        assert lazy.message_type is Assets
        assert lazy.to_binary() == assets.to_binary()
        untouched = lazy.to_binary()
        await _resolve(collection.ingest(result))
        assert [row.from_binary(value) for value in captured] == raw
        assert lazy.to_binary() is untouched  # Ingestion must not force decoding.
        for display in (repr(result), result._repr_html_()):
            for summary in ("Assets(1)", "Assets(0)", "Links(1)", "Storage(0 schemes)", "Authentication(0 schemes)"):
                assert summary in display

        decoded = lazy.get()
        assert lazy.get() is decoded
        decoded.assets[0].key = "edited"
        assert result.catalog[3].item().get().assets[0].key == "red"  # No shared cache.
        assert repr(lazy) == "Assets(1)"
        await _resolve(collection.ingest(result))
        written: Any = row.from_binary(captured[0])
        assert written.catalog.assets[0].key == "edited"
        assert written.catalog.to_binary().endswith(unknown)
        assert row.from_binary(captured[1]) == raw[1]
        found = await _resolve(target.find(UUID(int=3)))
        assert isinstance(found.catalog.item(), LazyMessage)
        assert found.catalog.item().get() == assets
        projected = await _resolve(target.query(temporal_extent=("1970", "1971"), skip_data=True))
        assert "catalog" not in projected

    record = {"time": "1970-01-01T00:00:01Z", "catalog": assets, "related": [LazyMessage(Assets, b""), assets]}
    for data in ([record], {key: [value] for key, value in record.items()}, pd.DataFrame([record])):
        await _resolve(collection.ingest(data))
        written = row.from_binary(captured[0])
        assert written.catalog == assets
        assert written.related == [Assets(), assets]
    for invalid in (b"", Links(), LazyMessage(Links, b"")):
        with pytest.raises(TypeError, match="Field 'catalog'"):
            await _resolve(collection.ingest([{**record, "catalog": invalid}]))


@given(st.lists(st.text(min_size=1, max_size=20), min_size=2, max_size=6, unique=True))
def test_split_singular_messages_merge_but_repeated_messages_stay_separate(keys: list[str]) -> None:
    schema = _schema()
    row = get_message_type(schema)
    converters = encoded_message_field_types(row)
    wire_row = get_message_type(schema, encoded_fields=converters)
    fragments = [Assets(assets=[Asset(key=key)]).to_binary() + b"\xa0\x06\x07" for key in keys]
    # Independently generate wire occurrences using the public protobuf schema.
    payload = b"".join(
        row(catalog=Assets.from_binary(part), related=[Assets.from_binary(part)]).to_binary() for part in fragments
    )
    converter = MessageToXarrayConverter(field_types=converters)
    converter.convert(wire_row.from_binary(payload))
    data = converter.finalize("time")
    lazy = data.catalog.item()
    assert lazy.to_binary() == b"".join(fragments)
    forwarded = to_messages(data, wire_row, field_types=converters)[0].to_binary()
    assert lazy.to_binary() == b"".join(fragments)
    restored: Any = row.from_binary(forwarded)
    assert [asset.key for asset in restored.catalog.assets] == keys
    assert [[asset.key for asset in group.assets] for group in restored.related] == [[key] for key in keys]
    assert [asset.key for asset in lazy.get().assets] == keys
    assert get_message_type(schema) is row  # Private schema never mutates the original.


@pytest.mark.parametrize("formatted", [False, True])
def test_invalid_lazy_message_defers_errors_until_get(formatted: bool) -> None:
    lazy = LazyMessage(
        Assets, b"\x1a\xff", repr_formatter=(lambda value: str(len(value.assets))) if formatted else None
    )
    assert repr(lazy) == "Assets(…)"
    assert lazy.to_binary() == b"\x1a\xff"
    with pytest.raises(ValueError, match="varint"):
        lazy.get()
    assert repr(lazy) == "Assets(…)"


def test_lazy_repr_formatter_uses_cached_mutable_message() -> None:
    payload = Assets(assets=[Asset(key="red")]).to_binary()
    plain = LazyMessage(Assets, payload)
    assert repr(plain) == "Assets(…)"
    assert plain.to_binary() is payload  # No formatter means no decoding.

    lazy = LazyMessage(Assets, payload, repr_formatter=lambda value: f"Assets({len(value.assets)})")
    assert repr(lazy) == "Assets(1)"
    message = lazy.get()
    message.assets.append(Asset(key="blue"))
    assert repr(lazy) == "Assets(2)"
    assert lazy.get() is message
    assert Assets.from_binary(lazy.to_binary()).assets == [Asset(key="red"), Asset(key="blue")]

    broken_formatter = LazyMessage(Assets, payload, repr_formatter=lambda value: value.assets[10].key)
    with pytest.raises(IndexError):
        repr(broken_formatter)
    assert broken_formatter.get().assets == [Asset(key="red")]


def test_lazy_xarray_equality_and_merge() -> None:
    schema = _schema()
    row = get_message_type(schema)
    field_types = encoded_message_field_types(row)
    wire_row = get_message_type(schema, encoded_fields=field_types)
    payload = row(time=Timestamp.from_seconds(1), catalog=Assets(assets=[Asset(key="red")])).to_binary()
    datasets = []
    for _ in range(2):
        converter = MessageToXarrayConverter(field_types=field_types)
        converter.convert(wire_row.from_binary(payload))
        datasets.append(converter.finalize("time"))
    left, right = datasets
    assert left.equals(right)
    assert left.equals(left.copy(deep=True))
    assert xr.merge([left, right], compat="no_conflicts").equals(left)

    right.catalog.item().get().assets[0].key = "blue"
    assert not left.equals(right)
    with pytest.raises(xr.MergeError, match="conflicting values"):
        xr.merge([left, right], compat="no_conflicts")


def test_lazy_nan_equality_matches_protobuf_before_and_after_display() -> None:
    payload = Assets(assets=[Asset(key="red", nodata=float("nan"))]).to_binary()
    converters = encoded_message_field_types(get_message_type(_schema()))
    left = converters["catalog"].from_proto([payload])
    right = converters["catalog"].from_proto([payload])
    # Native protobuf equality treats independently decoded NaNs as unequal.
    assert Assets.from_binary(payload) != Assets.from_binary(payload)
    for _ in range(2):
        assert left != right
        assert left != right.get()
        assert right.get() != left
        assert left == left  # noqa: PLR0124 -- reflexivity remains independent of NaN fields
        x = xr.Dataset({"assets": ("time", [left])})
        y = xr.Dataset({"assets": ("time", [right])})
        assert not x.equals(y)
        with pytest.raises(xr.MergeError, match="conflicting values"):
            xr.merge([x, y], compat="no_conflicts")
        assert repr(left) == "Assets(1)"


def test_lazy_equality_uses_message_values_not_wire_encoding() -> None:
    # Singular scalar duplicates obey last-one-wins; distinct bytes can mean the same message.
    first = Link(title="old").to_binary()
    last = Link(title="new").to_binary()
    left = LazyMessage(Link, first + last)
    right = LazyMessage(Link, last)
    assert left.to_binary() != right.to_binary()
    assert left == right
    assert left == Link(title="new")
    assert Link(title="new") == left
    assert left != LazyMessage(Assets, b"")
    assert left != None  # noqa: E711 -- exercise equality, not identity
    assert left != LazyMessage(Link, first)
    right.get().title = "edited"
    assert left != right
