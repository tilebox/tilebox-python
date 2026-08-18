import json
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from enum import Enum
from pathlib import Path, PurePosixPath
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import msgspec
import pyproj
import pytest
import shapely
from affine import Affine
from odc.geo import CRS, XY, AnchorEnum, BoundingBox, GeoBox, Geometry, Index2d, Resolution, Shape2d
from odc.geo.geobox import GeoboxTiles
from shapely.geometry import (
    GeometryCollection,
    LinearRing,
    LineString,
    MultiLineString,
    MultiPoint,
    MultiPolygon,
    Point,
    Polygon,
)

from tests.proto.test_pb2 import SampleArgs
from tilebox.datasets.data.data_access import SpatialFilter
from tilebox.datasets.query.id_interval import IDInterval
from tilebox.datasets.query.time_interval import TimeInterval
from tilebox.workflows.task import Task, deserialize_task, serialize_task


class StringEnum(Enum):
    VALUE = "value"


@dataclass(frozen=True)
class NestedValues:
    protobuf: SampleArgs
    path: Path


class StandardTypesTask(Task):
    aware_datetime: datetime
    naive_datetime: datetime
    date_value: date
    time_value: time
    duration: timedelta
    identifier: UUID
    decimal: Decimal
    enum: StringEnum
    binary: bytes
    mutable_binary: bytearray
    path: Path
    pure_path: PurePosixPath
    timezone: ZoneInfo
    values: set[int]
    frozen_values: frozenset[str]
    nested: NestedValues


def test_standard_types_round_trip() -> None:
    task = StandardTypesTask(
        aware_datetime=datetime(2024, 1, 2, 3, 4, 5, 6000, tzinfo=timezone.utc),
        naive_datetime=datetime(2024, 2, 3, 4, 5, 6, 7000),
        date_value=date(2024, 3, 4),
        time_value=time(5, 6, 7, 8000),
        duration=timedelta(days=-2, seconds=3, microseconds=4000),
        identifier=uuid4(),
        decimal=Decimal("1234567890.123456789"),
        enum=StringEnum.VALUE,
        binary=b"\x00\xffbinary",
        mutable_binary=bytearray(b"mutable"),
        path=Path("some/file.tif"),
        pure_path=PurePosixPath("another/file.tif"),
        timezone=ZoneInfo("Europe/Vienna"),
        values={1, 2, 3},
        frozen_values=frozenset({"a", "b"}),
        nested=NestedValues(SampleArgs(some_string="nested", some_int=42), Path("nested.tif")),
    )

    assert deserialize_task(StandardTypesTask, serialize_task(task)) == task


class RequiredIntTask(Task):
    value: int


class IntegerKeyTask(Task):
    value: dict[int, str]


class IntegerKeyAffineTask(Task):
    value: dict[int, Affine]


def test_msgspec_handles_native_validation_and_dictionary_keys() -> None:
    with pytest.raises(msgspec.ValidationError, match="Expected `int`, got `null`"):
        deserialize_task(RequiredIntTask, b"null")

    assert deserialize_task(IntegerKeyTask, b'{"1":"one"}') == IntegerKeyTask({1: "one"})
    assert deserialize_task(IntegerKeyAffineTask, b'{"1":[1,2,3,4,5,6]}') == IntegerKeyAffineTask(
        {1: Affine(1, 2, 3, 4, 5, 6)}
    )


def test_datetime_encoding_remains_compatible_with_the_old_decoder() -> None:
    class DatetimeTask(Task):
        value: datetime

    task = DatetimeTask(datetime(2024, 1, 2, 3, 4, 5, tzinfo=timezone.utc))
    assert serialize_task(task) == b'"2024-01-02T03:04:05+00:00"'


class DefaultsAndSkippedTask(Task):
    value: str
    defaulted: int = 42
    runtime_value: object = field(default=None, metadata={"skip_serialization": True})


def test_defaults_skipped_fields_and_old_json_are_supported() -> None:
    task = deserialize_task(DefaultsAndSkippedTask, b'{"value": "old payload"}')

    assert task == DefaultsAndSkippedTask("old payload")
    assert json.loads(serialize_task(DefaultsAndSkippedTask("new payload", runtime_value=object()))) == {
        "value": "new payload",
        "defaulted": 42,
    }


class NestedProtobufTask(Task):
    direct: SampleArgs
    values: list[SampleArgs]
    mapping: dict[str, SampleArgs]


def test_nested_protobuf_uses_base64_and_round_trips() -> None:
    message = SampleArgs(some_string="hello", some_int=123)
    task = NestedProtobufTask(message, [message], {"message": message})
    payload = json.loads(serialize_task(task))

    assert payload["direct"] == "CgVoZWxsbxB7"
    assert deserialize_task(NestedProtobufTask, serialize_task(task)) == task


class OptionalSingleProtobufTask(Task):
    value: SampleArgs | None


def test_optional_single_protobuf_preserves_raw_envelope() -> None:
    message = SampleArgs(some_string="hello", some_int=123)
    assert serialize_task(OptionalSingleProtobufTask(message)) == message.SerializeToString()
    assert deserialize_task(OptionalSingleProtobufTask, message.SerializeToString()) == OptionalSingleProtobufTask(
        message
    )
    assert deserialize_task(OptionalSingleProtobufTask, b"null") == OptionalSingleProtobufTask(None)


@pytest.mark.parametrize(
    "geometry",
    [
        Point(1, 2),
        MultiPoint([(1, 2), (3, 4)]),
        LineString([(0, 0), (1, 1)]),
        MultiLineString([[(0, 0), (1, 1)]]),
        LinearRing([(0, 0), (1, 0), (0, 1)]),
        Polygon([(0, 0), (1, 0), (0, 1)]),
        MultiPolygon([Polygon([(0, 0), (1, 0), (0, 1)])]),
        GeometryCollection([Point(1, 2), LineString([(0, 0), (1, 1)])]),
    ],
)
def test_shapely_geometry_families_round_trip(geometry: object) -> None:
    class GeometryTask(Task):
        value: shapely.Geometry

    result = deserialize_task(GeometryTask, serialize_task(GeometryTask(geometry))).value
    assert result.equals_exact(geometry, tolerance=0)
    assert type(result) is type(geometry)


def test_shapely_geometry_encodes_as_wkb() -> None:
    class GeometryTask(Task):
        value: shapely.Geometry

    geometry = Point(1, 2)
    assert serialize_task(GeometryTask(geometry)) == msgspec.json.encode(shapely.to_wkb(geometry))


def test_legacy_shapely_geojson_is_still_decodable() -> None:
    class GeometryTask(Task):
        value: shapely.Geometry

    task = deserialize_task(GeometryTask, b'{"type":"Point","coordinates":[1,2]}')
    assert task.value.equals_exact(Point(1, 2), tolerance=0)


class GeospatialTypesTask(Task):
    pyproj_crs: pyproj.CRS
    custom_pyproj_crs: pyproj.CRS
    affine: Affine
    odc_crs: CRS
    custom_odc_crs: CRS
    anchor: AnchorEnum
    geometry: Geometry
    geometry_without_crs: Geometry
    bbox: BoundingBox
    xy: XY
    resolution: Resolution
    index: Index2d
    shape: Shape2d
    geobox: GeoBox
    tiles: GeoboxTiles
    variable_tiles: GeoboxTiles


def test_geospatial_types_round_trip() -> None:
    geobox = GeoBox((6, 8), Affine(10, 1, 500000, 3, -10, 5400000), "EPSG:32633")
    task = GeospatialTypesTask(
        pyproj_crs=pyproj.CRS.from_epsg(32633),
        custom_pyproj_crs=pyproj.CRS.from_user_input("+proj=aeqd +lat_0=47 +lon_0=16 +datum=WGS84 +units=m +no_defs"),
        affine=Affine(10, 1, 500000, 3, -10, 5400000),
        odc_crs=CRS("EPSG:32633"),
        custom_odc_crs=CRS("+proj=longlat +a=6371000 +b=6371000 +no_defs"),
        anchor=AnchorEnum.CENTER,
        geometry=Geometry({"type": "Point", "coordinates": [16, 48]}, "EPSG:4326"),
        geometry_without_crs=Geometry({"type": "Point", "coordinates": [1, 2]}),
        bbox=BoundingBox(1, 2, 3, 4, "EPSG:4326"),
        xy=XY(1.5, 2.5),
        resolution=Resolution(10, -20),
        index=Index2d(3, 4),
        shape=Shape2d(8, 6),
        geobox=geobox,
        tiles=GeoboxTiles(geobox, (4, 3)),
        variable_tiles=GeoboxTiles(geobox, ((2, 4), (1, 3, 4))),
    )

    result = deserialize_task(GeospatialTypesTask, serialize_task(task))
    assert result.pyproj_crs == task.pyproj_crs
    assert result.custom_pyproj_crs == task.custom_pyproj_crs
    assert result.affine == task.affine
    assert result.odc_crs == task.odc_crs
    assert result.custom_odc_crs == task.custom_odc_crs
    assert result.anchor == task.anchor
    assert result.geometry == task.geometry
    assert result.geometry_without_crs == task.geometry_without_crs
    assert result.bbox == task.bbox
    assert result.xy == task.xy
    assert result.resolution == task.resolution
    assert result.index == task.index
    assert result.shape == task.shape
    assert result.geobox == task.geobox
    assert result.tiles.chunks == task.tiles.chunks
    assert result.variable_tiles.chunks == task.variable_tiles.chunks
    assert result.tiles.roi[1, 2] == task.tiles.roi[1, 2]


class TileboxTypesTask(Task):
    time_interval: TimeInterval
    id_interval: IDInterval
    spatial_filter: SpatialFilter


class TimeIntervalTask(Task):
    value: TimeInterval


def test_tilebox_types_round_trip_through_their_protobufs() -> None:
    task = TileboxTypesTask(
        TimeInterval(
            datetime(2024, 1, 1, tzinfo=timezone.utc),
            datetime(2024, 1, 2, tzinfo=timezone.utc),
            end_inclusive=True,
        ),
        IDInterval(uuid4(), uuid4(), start_exclusive=True, end_inclusive=False),
        SpatialFilter(Point(1, 2)),
    )

    result = deserialize_task(TileboxTypesTask, serialize_task(task))
    assert result.time_interval == task.time_interval
    assert result.id_interval == task.id_interval
    assert result.spatial_filter == task.spatial_filter


def test_legacy_time_interval_json_is_still_decodable() -> None:
    legacy_payload = (
        b'{"start":"2024-01-01T00:00:00+00:00","end":"2024-01-02T00:00:00+00:00",'
        b'"start_exclusive":false,"end_inclusive":true}'
    )
    expected = TimeInterval(
        datetime(2024, 1, 1, tzinfo=timezone.utc),
        datetime(2024, 1, 2, tzinfo=timezone.utc),
        end_inclusive=True,
    )
    assert deserialize_task(TimeIntervalTask, legacy_payload) == TimeIntervalTask(expected)


def test_async_geotiff_window_round_trip_when_installed() -> None:
    async_geotiff = pytest.importorskip("async_geotiff")

    class WindowTask(Task):
        window: async_geotiff.Window

    task = WindowTask(async_geotiff.Window(col_off=2, row_off=3, width=4, height=5))
    assert deserialize_task(WindowTask, serialize_task(task)) == task


def test_rasterio_window_round_trip_when_installed() -> None:
    rasterio_windows = pytest.importorskip("rasterio.windows")

    class WindowTask(Task):
        window: rasterio_windows.Window

    task = WindowTask(rasterio_windows.Window(col_off=2, row_off=3, width=4, height=5))
    assert deserialize_task(WindowTask, serialize_task(task)) == task


def test_optional_integrations_are_not_imported_by_task_module() -> None:
    script = """
import builtins
original_import = builtins.__import__
def guarded_import(name, *args, **kwargs):
    if name.startswith(('odc.geo', 'pyproj', 'affine', 'rasterio', 'async_geotiff')):
        raise ModuleNotFoundError(name)
    return original_import(name, *args, **kwargs)
builtins.__import__ = guarded_import
from tilebox.workflows.task import Task
class Example(Task):
    value: str
assert Example('works')._serialize() == b'\"works\"'
"""
    subprocess.run([sys.executable, "-c", script], check=True)  # noqa: S603


def test_invalid_value_reports_its_field() -> None:
    with pytest.raises(msgspec.ValidationError, match=r"Expected `object`.*at `\$\.mapping`"):
        deserialize_task(NestedProtobufTask, b'{"direct":"","values":[],"mapping":42}')


def test_unsupported_value_reports_its_type_and_field() -> None:
    with pytest.raises(TypeError, match=r"builtins\.object.*at \$\.defaulted"):
        serialize_task(DefaultsAndSkippedTask("value", defaulted=object()))  # ty: ignore[invalid-argument-type]
