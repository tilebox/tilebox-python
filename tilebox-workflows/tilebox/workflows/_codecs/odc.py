from typing import Any, cast

import msgspec
from affine import Affine
from odc.geo import CRS, XY, BoundingBox, GeoBox, Geometry, Index2d, Resolution, Shape2d
from odc.geo.geobox import GeoboxTiles
from shapely import to_geojson

from tilebox.workflows._codec import Codec, CodecRegistry


def _encode_crs(crs: CRS) -> str:
    authority = crs.authority
    return f"{authority[0]}:{authority[1]}" if authority and all(authority) else crs.wkt


def _encode_geometry(geometry: Geometry) -> dict[str, Any]:
    return {
        "geometry": msgspec.Raw(to_geojson(geometry.geom).encode()),
        "crs": _encode_crs(geometry.crs) if geometry.crs is not None else None,
    }


def _encode_bounding_box(bbox: BoundingBox) -> dict[str, Any]:
    return {
        "bounds": list(bbox),
        "crs": _encode_crs(bbox.crs) if bbox.crs is not None else None,
    }


def _encode_geobox(geobox: GeoBox) -> dict[str, Any]:
    return {
        "shape": [geobox.shape.y, geobox.shape.x],
        "affine": list(geobox.affine[:6]),
        "crs": _encode_crs(geobox.crs) if geobox.crs is not None else None,
    }


def _decode_geobox(value: dict[str, Any]) -> GeoBox:
    return GeoBox(value["shape"], Affine(*value["affine"]), value.get("crs"))


def _regular_chunks(chunks: tuple[int, ...]) -> bool:
    return bool(chunks) and all(chunk == chunks[0] for chunk in chunks[:-1]) and chunks[-1] <= chunks[0]


def _encode_geobox_tiles(tiles: GeoboxTiles) -> dict[str, Any]:
    y_chunks, x_chunks = tiles.chunks
    if _regular_chunks(y_chunks) and _regular_chunks(x_chunks):
        chunking = {"tile_shape": [y_chunks[0], x_chunks[0]]}
    else:
        chunking = {"chunks": {"y": list(y_chunks), "x": list(x_chunks)}}
    return {"base": _encode_geobox(cast(GeoBox, tiles.base)), "chunking": chunking}


def _decode_geobox_tiles(value: dict[str, Any]) -> GeoboxTiles:
    chunking = value["chunking"]
    chunks = chunking["tile_shape"] if "tile_shape" in chunking else (chunking["chunks"]["y"], chunking["chunks"]["x"])
    return GeoboxTiles(_decode_geobox(value["base"]), chunks)


def register(registry: CodecRegistry, _: type) -> None:
    registry.register(Codec(CRS, _encode_crs, CRS))
    registry.register(
        Codec(
            Geometry,
            _encode_geometry,
            lambda value: Geometry(value["geometry"], value.get("crs")),
        )
    )
    registry.register(
        Codec(
            BoundingBox,
            _encode_bounding_box,
            lambda value: BoundingBox(*value["bounds"], crs=value.get("crs")),
        )
    )
    for python_type in (XY, Resolution, Index2d, Shape2d):
        registry.register(
            Codec(
                python_type,
                lambda value: {"x": value.x, "y": value.y},
                lambda value, python_type=python_type: python_type(x=value["x"], y=value["y"]),
            )
        )
    registry.register(Codec(GeoBox, _encode_geobox, _decode_geobox))
    registry.register(Codec(GeoboxTiles, _encode_geobox_tiles, _decode_geobox_tiles))
