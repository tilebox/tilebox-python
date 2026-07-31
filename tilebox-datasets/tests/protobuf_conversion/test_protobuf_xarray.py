from uuid import UUID

import pandas as pd
import pytest
from google.protobuf import descriptor_pb2
from google.protobuf.descriptor_pool import Default
from google.protobuf.message_factory import GetMessageClass
from hypothesis import given, settings
from hypothesis.strategies import lists
from numpy.testing import assert_array_almost_equal, assert_array_equal
from pandas import to_datetime
from shapely import MultiPolygon, Polygon, from_wkb
from xarray.testing import assert_equal

from tests.data.datapoint import example_datapoints
from tests.example_dataset.example_dataset_pb2 import ExampleDatapoint
from tilebox.datasets.datasets.stac.v1.asset_pb import Assets
from tilebox.datasets.datasets.stac.v1.asset_pb2 import Asset as AssetPB2
from tilebox.datasets.datasets.stac.v1.asset_pb2 import Assets as AssetsPB2
from tilebox.datasets.datasets.stac.v1.authentication_pb import Authentication
from tilebox.datasets.datasets.stac.v1.authentication_pb2 import Authentication as AuthenticationPB2
from tilebox.datasets.datasets.stac.v1.core_pb import Links, Provider
from tilebox.datasets.datasets.stac.v1.core_pb2 import Link as LinkPB2
from tilebox.datasets.datasets.stac.v1.core_pb2 import Links as LinksPB2
from tilebox.datasets.datasets.stac.v1.core_pb2 import Provider as ProviderPB2
from tilebox.datasets.datasets.stac.v1.processing_pb import ProcessingSoftware
from tilebox.datasets.datasets.stac.v1.processing_pb2 import ProcessingSoftware as ProcessingSoftwarePB2
from tilebox.datasets.datasets.stac.v1.storage_pb import Storage
from tilebox.datasets.datasets.stac.v1.storage_pb2 import Storage as StoragePB2
from tilebox.datasets.protobuf_conversion.field_types import _AssetsDisplay
from tilebox.datasets.protobuf_conversion.protobuf_xarray import MessageToXarrayConverter
from tilebox.datasets.protobuf_conversion.to_protobuf import to_messages
from tilebox.datasets.query.time_interval import timestamp_to_datetime, us_to_datetime


@given(example_datapoints(generated_fields=True, missing_fields=False))
def test_convert_datapoint(datapoint: ExampleDatapoint) -> None:  # noqa: PLR0915
    converter = MessageToXarrayConverter()
    converter.convert(datapoint)
    dataset = converter.finalize("time")

    assert dataset.sizes["time"] == 1
    assert dataset.sizes["vec3"] == 3
    assert dataset.sizes["quaternion"] == 4
    assert dataset.sizes["n_some_repeated_string"] == len(datapoint.some_repeated_string)
    assert dataset.sizes["n_some_repeated_int"] == len(datapoint.some_repeated_int)
    assert dataset.sizes["n_some_repeated_bytes"] == len(datapoint.some_repeated_bytes)
    assert dataset.sizes["n_some_repeated_bool"] == len(datapoint.some_repeated_bool)
    assert dataset.sizes["n_some_repeated_time"] == len(datapoint.some_repeated_time)
    assert dataset.sizes["n_some_repeated_duration"] == len(datapoint.some_repeated_duration)
    assert dataset.sizes["n_some_repeated_identifier"] == len(datapoint.some_repeated_identifier)
    assert dataset.sizes["n_some_repeated_vec3"] == len(datapoint.some_repeated_vec3)
    assert dataset.sizes["n_some_repeated_geometry"] == len(datapoint.some_repeated_geometry)

    time = dataset.time.item()  # timestamp in nanoseconds from the numpy/xarray dataset
    assert us_to_datetime(to_datetime(time, utc=True).value // 1000) == timestamp_to_datetime(datapoint.time)
    assert dataset.id.item() == str(UUID(bytes=datapoint.id.uuid))
    ingestion_time = dataset.ingestion_time.item()  # timestamp in nanoseconds from the numpy/xarray dataset
    assert us_to_datetime(to_datetime(ingestion_time, utc=True).value // 1000) == timestamp_to_datetime(
        datapoint.ingestion_time
    )
    assert dataset.geometry.item() == from_wkb(datapoint.geometry.wkb)

    dataset = dataset.isel(time=0)  # select the only datapoint in the dataset
    assert dataset.some_string.item() == datapoint.some_string
    assert dataset.some_int.item() == datapoint.some_int
    assert dataset.some_double.item() == pytest.approx(datapoint.some_double)
    some_time = dataset.some_time.item()  # timestamp in nanoseconds from the numpy/xarray dataset
    assert us_to_datetime(to_datetime(some_time, utc=True).value // 1000) == timestamp_to_datetime(datapoint.some_time)
    assert dataset.some_duration.item() == int(datapoint.some_duration.seconds * 10**9 + datapoint.some_duration.nanos)

    assert dataset.some_bytes.item() == datapoint.some_bytes
    assert dataset.some_bool.item() == datapoint.some_bool

    assert dataset.some_identifier.item() == str(UUID(bytes=datapoint.some_identifier.uuid))
    assert_array_equal(
        dataset.some_vec3.to_numpy(), [datapoint.some_vec3.x, datapoint.some_vec3.y, datapoint.some_vec3.z]
    )
    assert_array_equal(
        dataset.some_quaternion.to_numpy(),
        [
            datapoint.some_quaternion.q1,
            datapoint.some_quaternion.q2,
            datapoint.some_quaternion.q3,
            datapoint.some_quaternion.q4,
        ],
    )

    assert isinstance(dataset.some_geometry.item(), Polygon | MultiPolygon)
    assert dataset.some_enum.item() == datapoint.some_enum

    assert list(dataset.some_repeated_string.to_numpy()) == list(datapoint.some_repeated_string)
    assert_array_equal(dataset.some_repeated_int.to_numpy(), datapoint.some_repeated_int)
    assert_array_almost_equal(dataset.some_repeated_double.to_numpy(), datapoint.some_repeated_double)
    assert list(dataset.some_repeated_bytes.to_numpy()) == list(datapoint.some_repeated_bytes)
    assert list(dataset.some_repeated_bool.to_numpy()) == list(datapoint.some_repeated_bool)

    expected_timestamps = [timestamp_to_datetime(t) for t in datapoint.some_repeated_time]
    actual_timestamps = [
        us_to_datetime(to_datetime(t, utc=True).value // 1000) for t in dataset.some_repeated_time.to_numpy()
    ]
    assert actual_timestamps == expected_timestamps

    expected_durations = [int(d.seconds * 10**9 + d.nanos) for d in datapoint.some_repeated_duration]
    actual_durations = [int(d) for d in dataset.some_repeated_duration.to_numpy()]
    assert actual_durations == expected_durations

    assert list(dataset.some_repeated_identifier.to_numpy()) == [
        str(UUID(bytes=u.uuid)) for u in datapoint.some_repeated_identifier
    ]

    expected_vec3 = [(v.x, v.y, v.z) for v in datapoint.some_repeated_vec3]
    actual_vec3 = [(v[0], v[1], v[2]) for v in dataset.some_repeated_vec3.to_numpy()]
    assert actual_vec3 == expected_vec3

    for i in range(len(datapoint.some_repeated_geometry)):
        assert isinstance(dataset.some_repeated_geometry[i].item(), Polygon | MultiPolygon)


def test_convert_stac_messages_to_protobuf_py() -> None:
    message_types = {
        "assets": ("datasets.stac.v1.Assets", AssetsPB2(assets=[AssetPB2(key="preview")]), _AssetsDisplay),
        "authentication": ("datasets.stac.v1.Authentication", AuthenticationPB2(), Authentication),
        "links": ("datasets.stac.v1.Links", LinksPB2(links=[LinkPB2(href="https://example.com")]), Links),
        "provider": ("datasets.stac.v1.Provider", ProviderPB2(name="Tilebox"), Provider),
        "processing_software": (
            "datasets.stac.v1.ProcessingSoftware",
            ProcessingSoftwarePB2(versions={"processor": "1.0"}),
            ProcessingSoftware,
        ),
        "storage": ("datasets.stac.v1.Storage", StoragePB2(), Storage),
    }
    file_descriptor = descriptor_pb2.FileDescriptorProto(
        name="tests/protobuf_conversion/stac_datapoint.proto",
        package="tests.protobuf_conversion",
        dependency=[
            "datasets/stac/v1/asset.proto",
            "datasets/stac/v1/authentication.proto",
            "datasets/stac/v1/core.proto",
            "datasets/stac/v1/processing.proto",
            "datasets/stac/v1/storage.proto",
        ],
    )
    message_descriptor = file_descriptor.message_type.add(name="StacDatapoint")
    for index, (field_name, (message_name, _, _)) in enumerate(message_types.items()):
        message_descriptor.field.add(
            name=field_name,
            number=index * 2 + 1,
            label=descriptor_pb2.FieldDescriptorProto.LABEL_OPTIONAL,
            type=descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE,
            type_name=f".{message_name}",
        )
        message_descriptor.field.add(
            name=f"related_{field_name}",
            number=index * 2 + 2,
            label=descriptor_pb2.FieldDescriptorProto.LABEL_REPEATED,
            type=descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE,
            type_name=f".{message_name}",
        )
    descriptor = Default().AddSerializedFile(file_descriptor.SerializeToString())
    message_type = GetMessageClass(descriptor.message_types_by_name["StacDatapoint"])

    values = {}
    for field_name, (_, source_value, _) in message_types.items():
        values[field_name] = source_value
        values[f"related_{field_name}"] = [source_value]
    messages = [message_type(), message_type(**values)]

    converter = MessageToXarrayConverter()
    converter.convert_all(messages)
    dataset = converter.finalize("time")

    for field_name, (_, source_value, target_type) in message_types.items():
        assert dataset[field_name].dtype == object
        assert dataset[field_name][0].item() is None
        converted_value = dataset[field_name][1].item()
        assert isinstance(converted_value, target_type)
        assert converted_value.to_binary() == source_value.SerializeToString()
        if field_name == "assets":
            assert isinstance(converted_value, Assets)
            assert str(converted_value) == "1 assets"
            assert repr(converted_value) == "[preview]"

        repeated_field_name = f"related_{field_name}"
        assert dataset[repeated_field_name].dtype == object
        converted_repeated_value = dataset[repeated_field_name][1, 0].item()
        assert isinstance(converted_repeated_value, target_type)
        assert converted_repeated_value.to_binary() == source_value.SerializeToString()

    converted_assets = dataset["assets"][1].item()
    assert isinstance(converted_assets, Assets)
    assert repr(converted_assets) == "[preview]"
    assert str(converted_assets) == "1 assets"

    roundtripped = to_messages(dataset, message_type)
    assert roundtripped == messages

    for repeated_container in (list, tuple):
        input_data = {}
        record = {}
        for field_name, (_, source_value, target_type) in message_types.items():
            value_type = Assets if field_name == "assets" else target_type
            target_value = value_type.from_binary(source_value.SerializeToString())
            input_data[field_name] = [target_value]
            input_data[f"related_{field_name}"] = [repeated_container([target_value])]
            record[field_name] = target_value
            record[f"related_{field_name}"] = repeated_container([target_value])
        assert to_messages(input_data, message_type) == [message_type(**values)]
        assert to_messages([record], message_type) == [message_type(**values)]

    html = dataset._repr_html_()
    assert "preview" in html
    assert "access_profiles" not in html


@given(lists(example_datapoints(generated_fields=True, missing_fields=True), min_size=5, max_size=30))
def test_convert_datapoints(datapoints: list[ExampleDatapoint]) -> None:  # noqa: C901, PLR0912
    converter = MessageToXarrayConverter()
    converter.convert_all(datapoints)
    dataset = converter.finalize("time")

    assert dataset.sizes["time"] == len(datapoints)

    # since fields are randomly missing, it can also be a field is missing for all datapoints
    # in which case it won't show up in the xarray dataset at all, which is why we have to check for this
    if "some_repeated_string" in dataset:
        n_some_repeated_string = max(len(dp.some_repeated_string) for dp in datapoints)
        assert dataset.sizes["n_some_repeated_string"] == n_some_repeated_string

    if "some_repeated_int" in dataset:
        n_some_repeated_int = max(len(dp.some_repeated_int) for dp in datapoints)
        assert dataset.sizes["n_some_repeated_int"] == n_some_repeated_int

    if "some_repeated_double" in dataset:
        n_some_repeated_double = max(len(dp.some_repeated_double) for dp in datapoints)
        assert dataset.sizes["n_some_repeated_double"] == n_some_repeated_double

    if "some_repeated_bytes" in dataset:
        n_some_repeated_bytes = max(len(dp.some_repeated_bytes) for dp in datapoints)
        assert dataset.sizes["n_some_repeated_bytes"] == n_some_repeated_bytes

    if "some_repeated_bool" in dataset:
        n_some_repeated_bool = max(len(dp.some_repeated_bool) for dp in datapoints)
        assert dataset.sizes["n_some_repeated_bool"] == n_some_repeated_bool

    if "some_repeated_time" in dataset:
        n_some_repeated_time = max(len(dp.some_repeated_time) for dp in datapoints)
        assert dataset.sizes["n_some_repeated_time"] == n_some_repeated_time

    if "some_repeated_duration" in dataset:
        n_some_repeated_duration = max(len(dp.some_repeated_duration) for dp in datapoints)
        assert dataset.sizes["n_some_repeated_duration"] == n_some_repeated_duration

    if "some_repeated_identifier" in dataset:
        n_some_repeated_identifier = max(len(dp.some_repeated_identifier) for dp in datapoints)
        assert dataset.sizes["n_some_repeated_identifier"] == n_some_repeated_identifier

    if "some_repeated_vec3" in dataset:
        n_some_repeated_vec3 = max(len(dp.some_repeated_vec3) for dp in datapoints)
        assert dataset.sizes["n_some_repeated_vec3"] == n_some_repeated_vec3

    if "some_repeated_geometry" in dataset:
        n_some_repeated_geometry = max(len(dp.some_repeated_geometry) for dp in datapoints)
        assert dataset.sizes["n_some_repeated_geometry"] == n_some_repeated_geometry

    if "some_id" in dataset:
        for uuid in dataset.some_id.to_numpy():
            assert isinstance(uuid, str)

    # strings should be stored as object arrays, with missing values (None or NaN) as fill
    if "some_string" in dataset:
        for string in dataset.some_string.to_numpy():
            assert pd.isna(string) or isinstance(string, str)
    if "some_repeated_string" in dataset:
        for string in dataset.some_repeated_string.to_numpy().ravel():
            assert pd.isna(string) or isinstance(string, str)

    # bytes should be stored as object arrays, with missing values (None or NaN) as fill
    if "some_bytes" in dataset:
        for bytes_ in dataset.some_bytes.to_numpy():
            assert pd.isna(bytes_) or isinstance(bytes_, bytes)
    if "some_repeated_bytes" in dataset:
        for bytes_ in dataset.some_repeated_bytes.to_numpy().ravel():
            assert pd.isna(bytes_) or isinstance(bytes_, bytes)


@given(lists(example_datapoints(missing_fields=True), min_size=1, max_size=10))
@settings(max_examples=10)
def test_convert_datapoints_all_at_once_or_one_by_one_same_result(
    datapoints: list[ExampleDatapoint],
) -> None:
    converter1 = MessageToXarrayConverter()
    converter2 = MessageToXarrayConverter()
    converter1.convert_all(datapoints)
    for dp in datapoints:
        converter2.convert(dp)

    dataset1 = converter1.finalize("time")
    dataset2 = converter2.finalize("time")

    assert_equal(dataset1, dataset2)
