"""GeoTIFF coordinate helpers."""

import math
import sys

from pyproj import CRS, Proj, Transformer

try:
    from async_geotiff import GeoTIFF, Window
except ImportError:
    if sys.version_info < (3, 11):
        raise ImportError(
            "tilebox.storage.geotiff is unavailable on Python 3.10 because async-geotiff requires Python 3.11 or newer"
        ) from None
    raise ImportError("async-geotiff is required by tilebox-storage but could not be imported") from None

Bounds = tuple[float, float, float, float]
BoundsCRS = str | int | CRS | Proj


def window_from_bounds(  # noqa: C901
    geotiff: GeoTIFF,
    bounds: Bounds,
    *,
    crs: BoundsCRS,
    require_fully_contained: bool = False,
) -> Window:
    """Convert geographic bounds to an outward-rounded GeoTIFF pixel window.

    This helper is useful before calling async-geotiff window-reading methods. It
    transforms ``bounds`` from ``crs`` into the image CRS, maps all four corners
    through the inverse image transform, rounds outward so intersecting pixels are
    retained, and clips the result to the image dimensions.

    Args:
        geotiff: Open async-geotiff image whose CRS, affine transform, width, and
            height define the output pixel coordinate space.
        bounds: Four coordinates in explicit ``(left, bottom, right, top)`` order,
            also known as ``(min_x, min_y, max_x, max_y)``.
        crs: CRS of ``bounds`` as an EPSG integer, user-input string, ``CRS``, or
            ``Proj`` instance.
        require_fully_contained: Reject bounds extending beyond the image instead of
            clipping them to the image dimensions.

    Returns:
        An async-geotiff ``Window`` containing every pixel touched by the bounds.

    Raises:
        ValueError: If bounds are malformed, cross the EPSG:4326 antimeridian, cannot
            be transformed, do not intersect the image, or violate full containment.
    """
    try:
        valid_bounds = len(bounds) == 4 and all(math.isfinite(value) for value in bounds)
    except TypeError:
        valid_bounds = False
    if not valid_bounds:
        raise ValueError("bounds must contain four finite values in (left, bottom, right, top) order")
    left, bottom, right, top = bounds
    try:
        source_crs = CRS.from_user_input(crs)
    except Exception as error:
        raise ValueError(f"invalid bounds CRS: {crs!r}") from error
    if left > right:
        if source_crs.to_epsg() == 4326:
            raise ValueError("antimeridian-crossing bounds are not supported; split the bounds at the antimeridian")
        raise ValueError("bounds left must be less than or equal to right")
    if bottom > top:
        raise ValueError("bounds bottom must be less than or equal to top")
    try:
        transformed = Transformer.from_crs(source_crs, geotiff.crs, always_xy=True).transform_bounds(
            *bounds,
            densify_pts=21,
        )
    except Exception as error:
        raise ValueError("bounds could not be transformed into the GeoTIFF CRS") from error
    if not all(math.isfinite(value) for value in transformed):
        raise ValueError("bounds could not be transformed into finite GeoTIFF coordinates")
    left, bottom, right, top = transformed
    try:
        inverse = ~geotiff.transform
        pixels = [inverse * (x, y) for x in (left, right) for y in (bottom, top)]
    except Exception as error:
        raise ValueError("GeoTIFF transform is not invertible") from error
    col_start = math.floor(min(point[0] for point in pixels))
    col_stop = math.ceil(max(point[0] for point in pixels))
    row_start = math.floor(min(point[1] for point in pixels))
    row_stop = math.ceil(max(point[1] for point in pixels))
    outside = col_start < 0 or row_start < 0 or col_stop > geotiff.width or row_stop > geotiff.height
    if require_fully_contained and outside:
        raise ValueError("Requested bounds are not fully contained in the GeoTIFF")
    col_start, row_start = max(0, col_start), max(0, row_start)
    col_stop, row_stop = min(geotiff.width, col_stop), min(geotiff.height, row_stop)
    if col_start >= col_stop or row_start >= row_stop:
        raise ValueError("Requested bounds do not intersect the GeoTIFF")
    return Window(
        col_off=col_start,
        row_off=row_start,
        width=col_stop - col_start,
        height=row_stop - row_start,
    )
