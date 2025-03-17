from google.protobuf import duration_pb2, timestamp_pb2
from hypothesis.strategies import (
    DrawFn,
    booleans,
    composite,
    floats,
    integers,
    sampled_from,
    uuids,
)
from shapely import MultiPolygon, Polygon, box, to_wkb

from tests.data.time_interval import i64_datetimes
from tilebox.datasets.data.time_interval import datetime_to_timestamp
from tilebox.datasets.datasetsv1 import well_known_types_pb2


@composite
def datetime_messages(draw: DrawFn) -> timestamp_pb2.Timestamp:
    return datetime_to_timestamp(draw(i64_datetimes))


@composite
def duration_messages(draw: DrawFn) -> duration_pb2.Duration:
    return duration_pb2.Duration(
        seconds=draw(integers(min_value=0, max_value=1000000000)),
        nanos=draw(integers(min_value=0, max_value=1000000000 - 1)),
    )


@composite
def uuid_messages(draw: DrawFn) -> well_known_types_pb2.UUID:
    return well_known_types_pb2.UUID(uuid=draw(uuids(version=4)).bytes)


@composite
def vec3_messages(draw: DrawFn) -> well_known_types_pb2.Vec3:
    return well_known_types_pb2.Vec3(
        x=draw(floats(min_value=-100, max_value=100)),
        y=draw(floats(min_value=-100, max_value=100)),
        z=draw(floats(min_value=-100, max_value=100)),
    )


@composite
def quaternion_messages(draw: DrawFn) -> well_known_types_pb2.Quaternion:
    return well_known_types_pb2.Quaternion(
        q1=draw(floats(min_value=-1, max_value=1)),
        q2=draw(floats(min_value=-1, max_value=1)),
        q3=draw(floats(min_value=-1, max_value=1)),
        q4=draw(floats(min_value=-1, max_value=1)),
    )


@composite
def latlon_messages(draw: DrawFn) -> well_known_types_pb2.LatLon:
    return well_known_types_pb2.LatLon(
        latitude=draw(floats(min_value=-90, max_value=90)),
        longitude=draw(floats(min_value=-180, max_value=180)),
    )


@composite
def latlonalt_messages(draw: DrawFn) -> well_known_types_pb2.LatLonAlt:
    return well_known_types_pb2.LatLonAlt(
        latitude=draw(floats(min_value=-90, max_value=90)),
        longitude=draw(floats(min_value=-180, max_value=180)),
        altitude=draw(floats(min_value=-100, max_value=1000)),
    )


@composite
def geobuf_messages(draw: DrawFn) -> well_known_types_pb2.GeobufData:
    encoded_geobufs = [
        # POLYGON ((-24.7917 80.1388, -20.6726 80.9065, -42.9612 82.8902, -45.6082 81.9369, -24.7917 80.1388))
        b"\x10\x02\x18\x042\x1e\x08\x05\x12\x01\x04\x1a\x17\xd9\xa1\x1e\xd8\xe9a\xce\x83\x05\xfaw\xcb\x9a\x1b\xfa\xb5\x02\xcb\x9d\x03\xf9\x94\x01",
        # POLYGON ((37.1165 82.5691, 60.97982545 85.05115, 3.218114686 85.05115, 3.0578 83.8312, 37.1165 82.5691))
        b"\x10\x02\x18\t2/\x08\x05\x12\x01\x04\x1a(\xc0\xe0\x86\xc5\x94\x02\xc0\xeb\x83\x98\xe7\x04\x94\xcc\xeb\xe5\xb1\x01\xa0\xcf\x88\xbf\x12\xd7\x8a\xee\xad\xae\x03\x00\xfb\xd4\xf1\x98\x01\xdf\xd6\xb7\x8b\t",
    ]
    data = draw(sampled_from(encoded_geobufs))
    return well_known_types_pb2.GeobufData.FromString(data)


@composite
def shapely_polygons(draw: DrawFn) -> Polygon:
    xmin = draw(floats(min_value=-180, max_value=160))
    ymin = draw(floats(min_value=-90, max_value=70))

    width = draw(floats(min_value=1, max_value=20))
    height = draw(floats(min_value=1, max_value=20))

    return box(xmin, ymin, xmin + width, ymin + height)


@composite
def geometry_messages(draw: DrawFn) -> well_known_types_pb2.Geometry:
    is_multi = draw(booleans())
    geom = draw(shapely_polygons())
    if is_multi:
        other = draw(shapely_polygons())
        geom = MultiPolygon([geom, other])

    return well_known_types_pb2.Geometry(wkb=to_wkb(geom))


@composite
def processing_levels(draw: DrawFn) -> well_known_types_pb2.ProcessingLevel:
    return draw(
        sampled_from(
            [
                well_known_types_pb2.ProcessingLevel.PROCESSING_LEVEL_L0,
                well_known_types_pb2.ProcessingLevel.PROCESSING_LEVEL_L1,
                well_known_types_pb2.ProcessingLevel.PROCESSING_LEVEL_L1A,
            ]
        )
    )
