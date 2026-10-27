from hypothesis.strategies import (
    DrawFn,
    booleans,
    composite,
    floats,
    integers,
    sampled_from,
    uuids,
)
from protobuf.wkt.google.protobuf import duration_pb, timestamp_pb
from shapely import MultiPolygon, Polygon, box, to_wkb

from tests.query.time_interval import i64_datetimes
from tilebox.datasets.query.time_interval import datetime_to_timestamp
from tilebox.datasets.v1 import well_known_types_pb


@composite
def datetime_messages(draw: DrawFn) -> timestamp_pb.Timestamp:
    return datetime_to_timestamp(draw(i64_datetimes))


@composite
def duration_messages(draw: DrawFn) -> duration_pb.Duration:
    return duration_pb.Duration(
        seconds=draw(integers(min_value=0, max_value=1000000000)),
        nanos=draw(integers(min_value=0, max_value=1000000000 - 1)),
    )


@composite
def uuid_messages(draw: DrawFn) -> well_known_types_pb.UUID:
    return well_known_types_pb.UUID(uuid=draw(uuids(version=4)).bytes)


@composite
def vec3_messages(draw: DrawFn) -> well_known_types_pb.Vec3:
    return well_known_types_pb.Vec3(
        x=draw(floats(min_value=-100, max_value=100)),
        y=draw(floats(min_value=-100, max_value=100)),
        z=draw(floats(min_value=-100, max_value=100)),
    )


@composite
def quaternion_messages(draw: DrawFn) -> well_known_types_pb.Quaternion:
    return well_known_types_pb.Quaternion(
        q1=draw(floats(min_value=-1, max_value=1)),
        q2=draw(floats(min_value=-1, max_value=1)),
        q3=draw(floats(min_value=-1, max_value=1)),
        q4=draw(floats(min_value=-1, max_value=1)),
    )


@composite
def latlon_messages(draw: DrawFn) -> well_known_types_pb.LatLon:
    return well_known_types_pb.LatLon(
        latitude=draw(floats(min_value=-90, max_value=90)),
        longitude=draw(floats(min_value=-180, max_value=180)),
    )


@composite
def latlonalt_messages(draw: DrawFn) -> well_known_types_pb.LatLonAlt:
    return well_known_types_pb.LatLonAlt(
        latitude=draw(floats(min_value=-90, max_value=90)),
        longitude=draw(floats(min_value=-180, max_value=180)),
        altitude=draw(floats(min_value=-100, max_value=1000)),
    )


@composite
def shapely_polygons(draw: DrawFn) -> Polygon:
    xmin = draw(floats(min_value=-180, max_value=160))
    ymin = draw(floats(min_value=-90, max_value=70))

    width = draw(floats(min_value=1, max_value=20))
    height = draw(floats(min_value=1, max_value=20))

    return box(xmin, ymin, xmin + width, ymin + height)


@composite
def geometry_messages(draw: DrawFn) -> well_known_types_pb.Geometry:
    is_multi = draw(booleans())
    geom = draw(shapely_polygons())
    if is_multi:
        other = draw(shapely_polygons())
        geom = MultiPolygon([geom, other])

    return well_known_types_pb.Geometry(wkb=to_wkb(geom))


@composite
def processing_levels(draw: DrawFn) -> well_known_types_pb.ProcessingLevel:
    return draw(
        sampled_from(
            [
                well_known_types_pb.ProcessingLevel.L0,
                well_known_types_pb.ProcessingLevel.L1,
                well_known_types_pb.ProcessingLevel.L1A,
            ]
        )
    )
