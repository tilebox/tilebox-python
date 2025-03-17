from uuid import UUID

import pytest
from hypothesis import given, settings
from hypothesis.strategies import lists
from numpy.testing import assert_array_almost_equal, assert_array_equal
from pandas import to_datetime
from shapely import MultiPolygon, Polygon
from xarray.testing import assert_equal

from tests.data.datapoint import datapoint_pages, datapoints, example_datapoints
from tests.example_dataset.example_dataset_pb2 import ExampleDatapoint
from tilebox.datasets.data.datapoint import Datapoint, DatapointPage
from tilebox.datasets.data.time_interval import timestamp_to_datetime, us_to_datetime
from tilebox.datasets.datasetsv1.well_known_types_pb2 import ProcessingLevel
from tilebox.datasets.protobuf_conversion.protobuf_xarray import (
    MessageToXarrayConverter,
    TimeseriesToXarrayConverter,
)


@given(example_datapoints(missing_fields=False))
def test_convert_datapoint(datapoint: ExampleDatapoint) -> None:  # noqa: PLR0915
    converter = MessageToXarrayConverter()
    converter.convert(datapoint)
    dataset = converter.finalize("time")

    assert dataset.sizes["time"] == 1
    assert dataset.sizes["vec3"] == 3
    assert dataset.sizes["quaternion"] == 4
    assert dataset.sizes["latlon"] == 2
    assert dataset.sizes["lat_lon_alt"] == 3
    assert dataset.sizes["n_some_repeated_string"] == len(datapoint.some_repeated_string)
    assert dataset.sizes["n_some_repeated_int"] == len(datapoint.some_repeated_int)
    assert dataset.sizes["n_some_repeated_bytes"] == len(datapoint.some_repeated_bytes)
    assert dataset.sizes["n_some_repeated_bool"] == len(datapoint.some_repeated_bool)
    assert dataset.sizes["n_some_repeated_time"] == len(datapoint.some_repeated_time)
    assert dataset.sizes["n_some_repeated_duration"] == len(datapoint.some_repeated_duration)
    assert dataset.sizes["n_some_repeated_identifier"] == len(datapoint.some_repeated_identifier)
    assert dataset.sizes["n_some_repeated_vec3"] == len(datapoint.some_repeated_vec3)
    assert dataset.sizes["n_some_repeated_geometry"] == len(datapoint.some_repeated_geometry)

    dataset = dataset.isel(time=0)  # select the only datapoint in the dataset
    assert dataset.some_string.item() == datapoint.some_string
    assert dataset.some_int.item() == datapoint.some_int
    assert dataset.some_double.item() == pytest.approx(datapoint.some_double)
    time = dataset.some_time.item()  # timestamp in nanoseconds from the numpy/xarray dataset
    assert us_to_datetime(to_datetime(time, utc=True).value // 1000) == timestamp_to_datetime(datapoint.some_time)
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
    assert_array_equal(
        dataset.some_latlon.to_numpy(), [datapoint.some_latlon.latitude, datapoint.some_latlon.longitude]
    )
    assert_array_equal(
        dataset.some_latlon_alt.to_numpy(),
        [datapoint.some_latlon_alt.latitude, datapoint.some_latlon_alt.longitude, datapoint.some_latlon_alt.altitude],
    )
    assert isinstance(dataset.some_geometry.item(), Polygon | MultiPolygon)
    expected_level = {v: k for k, v in ProcessingLevel.items()}[datapoint.some_enum].removeprefix("PROCESSING_LEVEL_")
    assert dataset.some_enum.item() == expected_level

    assert_array_equal(dataset.some_repeated_string.to_numpy(), datapoint.some_repeated_string)
    assert_array_equal(dataset.some_repeated_int.to_numpy(), datapoint.some_repeated_int)
    assert_array_almost_equal(dataset.some_repeated_double.to_numpy(), datapoint.some_repeated_double)

    assert list(dataset.some_repeated_string.to_numpy()) == list(datapoint.some_repeated_string)
    assert list(dataset.some_repeated_int.to_numpy()) == list(datapoint.some_repeated_int)
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


@given(datapoints(missing_fields=True))
def test_convert_timeseries_datapoint(datapoint: Datapoint) -> None:
    converter = TimeseriesToXarrayConverter()
    converter.convert(datapoint)
    dataset = converter.finalize()

    assert dataset.sizes["time"] == 1
    assert dataset.id.item() == datapoint.meta.id
    event_time = dataset.time.item() // 1000
    assert us_to_datetime(event_time) == timestamp_to_datetime(datapoint.meta.event_time)
    ingestion_time = dataset.ingestion_time.item() // 1000
    assert us_to_datetime(ingestion_time) == timestamp_to_datetime(datapoint.meta.ingestion_time)


@given(lists(example_datapoints(missing_fields=True), min_size=5, max_size=30))
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

    # strings should be stored as object arrays, with None as the fill value if missing
    if "some_string" in dataset:
        for string in dataset.some_string.to_numpy():
            assert string is None or isinstance(string, str)
    if "some_repeated_string" in dataset:
        for string in dataset.some_repeated_string.to_numpy().ravel():
            assert string is None or isinstance(string, str)

    # bytes should be stored as object arrays, with None as the fill value if missing
    if "some_bytes" in dataset:
        for bytes_ in dataset.some_bytes.to_numpy():
            assert bytes_ is None or isinstance(bytes_, bytes)
    if "some_repeated_bytes" in dataset:
        for bytes_ in dataset.some_repeated_bytes.to_numpy().ravel():
            assert bytes_ is None or isinstance(bytes_, bytes)


@given(datapoint_pages(empty_next_page=True, missing_fields=True))
def test_convert_timeseries_datapoints(page: DatapointPage) -> None:
    converter = TimeseriesToXarrayConverter()
    converter.convert_all(page)
    dataset = converter.finalize()

    assert dataset.sizes["time"] == len(page.meta)
    for i in range(len(page.meta)):
        datapoint = dataset.isel(time=i)
        meta = page.meta[i]
        assert datapoint.id.item() == meta.id
        event_time = datapoint.time.item() // 1000
        assert us_to_datetime(event_time) == timestamp_to_datetime(meta.event_time)
        ingestion_time = datapoint.ingestion_time.item() // 1000
        assert us_to_datetime(ingestion_time) == timestamp_to_datetime(meta.ingestion_time)


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
