import numpy as np
from shapely import MultiPolygon, Polygon

from tilebox.datasets.datasetsv1.well_known_types_pb2 import GeobufData


def parse_geobuf(data: GeobufData) -> Polygon | MultiPolygon:
    if data.dimensions != 2:
        raise ValueError(f"Expected GeobufData message with 2 dimensions but got {data.dimensions}")

    coords = np.asarray(data.geometry.coords)
    if data.geometry.type == GeobufData.Geometry.Type.TYPE_POLYGON:
        return _decode_polygon_geobuf(coords, np.asarray(data.geometry.lengths), data.precision)
    if data.geometry.type == GeobufData.Geometry.Type.TYPE_MULTIPOLYGON:
        return _decode_multipolygon_geobuf(coords, np.asarray(data.geometry.lengths), data.precision)

    raise ValueError(f"Unsupported geometry type {data.geometry.type}")


def _decode_multipolygon_geobuf(coords: np.ndarray, lengths: np.ndarray, precision: int) -> MultiPolygon:
    """Convert geobuf encoded coordinates and lengths to a shapely multipolygon.

    A multipolygon is a sequence of polygons. The lengths array tells us how many polygons we
    have, and also how many individual coordiante rings each polygon consists of.

    We can therefore iterate over that and then use _decode_polygon_geobuf to convert
    each polygon individually, and afterwards assemble it back together.
    """
    polygons = []

    # let's now construct our multipolygon as a sequence of polygons
    n_polys = lengths[0]
    curr_len_idx = 1  # first value is the number of polygons
    curr_coord_idx = 0
    while curr_len_idx < len(lengths):
        n_rings = lengths[curr_len_idx]
        curr_len_idx += 1

        poly_lengths = lengths[curr_len_idx : curr_len_idx + n_rings]
        n_poly_coords = np.sum(poly_lengths) * 2  # * 2 for lat/lon
        poly_coords = coords[curr_coord_idx : curr_coord_idx + n_poly_coords]
        polygons.append(_decode_polygon_geobuf(poly_coords, poly_lengths, precision))

        curr_len_idx += n_rings
        curr_coord_idx += n_poly_coords

    if len(polygons) != n_polys:
        raise ValueError("Number of polygons does not match the number of polygons in the lengths array")

    return MultiPolygon(polygons)


def _decode_polygon_geobuf(coords: np.ndarray, lengths: np.ndarray, precision: int) -> Polygon:
    """Convert geobuf encoded coordinates and lengths to a shapely polygon.

    A polygon is a sequence of rings (list of points). The simplest case is just one ring,
    which is the outer shell of the polygon. All subsequent rings are holes in the interior
    of the polygon.

    Args:
        coords: Flat list of coordinates in geobuf encoding
        lengths: Lengths of the individual rings that make up this polygon. Correspond to
            the coords.
        precision: Precision multiplier for the coordinates

    Returns:
        A shapely polygon
    """
    rings = []
    curr_idx = 0

    for ring_length in lengths:
        rings.append(_decode_coords_ring(coords[curr_idx : curr_idx + ring_length * 2], precision))  # * 2 for lon/lat
        curr_idx += ring_length * 2

    if len(rings) < 1:
        raise ValueError("Polygon needs to consist of at least one ring")

    return Polygon(shell=rings[0], holes=rings[1:])


def _decode_coords_ring(coords: np.ndarray, precision: int) -> list[tuple[float, float]]:
    """Convert a geobuf encoded coord ring to a list of points

    Geobuf encoding is as follows:
    All values are stored as integers, by multiplying them with the precision (e.g. 10^7 for precision 7)
    Then all values are delta encoded, i.e. the first value is stored as is, and all following values are
    stored as the difference to the previous value.
    The values are then zigzag encoded, e.g. first an x value, then a y value, then the next x value, etc.
    All polygons need to be closed, i.e. the first and last point need to be the same. However, geobuf skips
    that last (duplicated) value, so we need to add it back in.

    Returns:
        A list of points
    """
    precision = 10**precision
    lons = np.cumsum(coords[::2]) / precision
    lats = np.cumsum(coords[1::2]) / precision
    points = list(zip(lons, lats, strict=True))
    points.append(points[0])  # close the ring
    return points
