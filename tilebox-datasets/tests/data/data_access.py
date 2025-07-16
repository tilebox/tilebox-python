from typing import Literal

from hypothesis.strategies import DrawFn, booleans, composite, none, one_of, sampled_from
from shapely import Geometry

from tests.data.well_known_types import shapely_polygons
from tests.query.datapoint import id_intervals
from tests.query.time_interval import time_intervals
from tilebox.datasets.data.data_access import (
    QueryFilters,
    SpatialCoordinateSystem,
    SpatialFilter,
    SpatialFilterDict,
    SpatialFilterMode,
)


@composite
def spatial_filter_likes(draw: DrawFn) -> Geometry | SpatialFilterDict:
    """
    A hypothesis strategy for generating random spatial filter like values, that can be converted to a spatial filter
    """
    geometry = draw(shapely_polygons())
    as_plain_polygon = draw(booleans())
    if as_plain_polygon:
        return geometry

    # return a dict
    mode: SpatialFilterMode | Literal["intersects", "contains"] | None = draw(
        sampled_from(["intersects", "contains"]), sampled_from(SpatialFilterMode) | none()
    )
    coordinate_system: SpatialCoordinateSystem | Literal["cartesian", "spherical"] | None = draw(
        sampled_from(["cartesian", "spherical"]), sampled_from(SpatialCoordinateSystem) | none()
    )
    include_mode = draw(booleans())
    include_coordinate_system = draw(booleans())
    if include_mode and include_coordinate_system:
        return {"geometry": geometry, "mode": mode, "coordinate_system": coordinate_system}
    if include_mode:
        return {"geometry": geometry, "mode": mode}
    if include_coordinate_system:
        return {"geometry": geometry, "coordinate_system": coordinate_system}
    return {"geometry": geometry}


@composite
def spatial_filters(draw: DrawFn) -> SpatialFilter:
    """A hypothesis strategy for generating random spatial filters"""
    geometry = draw(shapely_polygons())
    mode = draw(sampled_from(SpatialFilterMode) | none())
    coordinate_system = draw(sampled_from(SpatialCoordinateSystem) | none())
    return SpatialFilter(geometry, mode, coordinate_system)


@composite
def query_filters(draw: DrawFn) -> QueryFilters:
    """A hypothesis strategy for generating random query filters"""
    temporal_extent = draw(one_of(time_intervals(), id_intervals()))
    spatial_extent = draw(spatial_filters() | none())
    return QueryFilters(temporal_extent, spatial_extent)
