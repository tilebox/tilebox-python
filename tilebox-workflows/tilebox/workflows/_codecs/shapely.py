from typing import Any

import msgspec
from shapely import Geometry, from_geojson, from_wkb, to_wkb
from shapely.geometry import LinearRing, mapping, shape

from tilebox.workflows._codec import Codec, CodecRegistry


def _encode_geometry(geometry: Geometry) -> object:
    if isinstance(geometry, LinearRing):
        return mapping(geometry)
    return to_wkb(geometry)


def _decode_geometry(value: Any) -> Geometry:
    if isinstance(value, str):
        return from_wkb(msgspec.convert(value, type=bytes))
    if isinstance(value, dict) and value.get("type") == "LinearRing":
        return shape(value)
    return from_geojson(msgspec.json.encode(value))


def register(registry: CodecRegistry, _: type) -> None:
    registry.register(Codec(Geometry, _encode_geometry, _decode_geometry))
