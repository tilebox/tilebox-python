from dataclasses import dataclass
from enum import Enum
from typing import Literal, TypeAlias, TypedDict

from shapely import Geometry, from_wkb, to_wkb

# from python 3.11 onwards this is available as typing.NotRequired:
from typing_extensions import NotRequired

from tilebox.datasets.datasets.v1 import data_access_pb2, well_known_types_pb2
from tilebox.datasets.query.id_interval import IDInterval
from tilebox.datasets.query.time_interval import TimeInterval


class SpatialFilterMode(Enum):
    INTERSECTS = data_access_pb2.SPATIAL_FILTER_MODE_INTERSECTS
    CONTAINS = data_access_pb2.SPATIAL_FILTER_MODE_CONTAINS


_filter_modes_from_string = {mode.name.lower(): mode for mode in SpatialFilterMode}
_filter_mode_int_to_enum = {mode.value: mode for mode in SpatialFilterMode}


class SpatialCoordinateSystem(Enum):
    CARTESIAN = data_access_pb2.SPATIAL_COORDINATE_SYSTEM_CARTESIAN
    SPHERICAL = data_access_pb2.SPATIAL_COORDINATE_SYSTEM_SPHERICAL


_coordinate_systems_from_string = {system.name.lower(): system for system in SpatialCoordinateSystem}
_coordinate_system_int_to_enum = {system.value: system for system in SpatialCoordinateSystem}


class SpatialFilterDict(TypedDict):
    geometry: Geometry
    mode: NotRequired[SpatialFilterMode | Literal["intersects", "contains"]]
    coordinate_system: NotRequired[SpatialCoordinateSystem | Literal["cartesian", "spherical"]]


SpatialFilterLike: TypeAlias = Geometry | SpatialFilterDict


@dataclass(frozen=True)
class SpatialFilter:
    """
    A spatial filter defines a spatial filter operation as part of a query.

    The spatial filter operation is defined by the geometry, mode and coordinate system.

    Args:
        geometry: The spatial geometry to filter by (e.g. a polygon)
        mode: The spatial filter mode to use. Can be one of "intersects" or "contains".
            Defaults to "intersects".
        crs: The coordinate system to use for performing geometry calculations. Can be one
            of "cartesian" or "spherical".
    """

    geometry: Geometry
    mode: SpatialFilterMode | None = None
    coordinate_system: SpatialCoordinateSystem | None = None

    @classmethod
    def from_message(cls, filter_message: data_access_pb2.SpatialFilter) -> "SpatialFilter":
        return SpatialFilter(
            geometry=from_wkb(filter_message.geometry.wkb),
            mode=_filter_mode_int_to_enum.get(filter_message.mode, None),
            coordinate_system=_coordinate_system_int_to_enum.get(filter_message.coordinate_system, None),
        )

    def to_message(self) -> data_access_pb2.SpatialFilter:
        filter_mode = self.mode.value if self.mode else data_access_pb2.SPATIAL_FILTER_MODE_UNSPECIFIED
        coordinate_system = (
            self.coordinate_system.value
            if self.coordinate_system
            else data_access_pb2.SPATIAL_COORDINATE_SYSTEM_UNSPECIFIED
        )

        return data_access_pb2.SpatialFilter(
            geometry=well_known_types_pb2.Geometry(wkb=to_wkb(self.geometry)),
            mode=filter_mode,
            coordinate_system=coordinate_system,
        )

    @classmethod
    def parse(cls, spatial_filter_like: SpatialFilterLike) -> "SpatialFilter":
        if isinstance(spatial_filter_like, SpatialFilter):
            return spatial_filter_like

        if isinstance(spatial_filter_like, Geometry):
            return SpatialFilter(spatial_filter_like)

        if isinstance(spatial_filter_like, dict):
            mode = spatial_filter_like.get("mode", None)
            if isinstance(mode, str):
                mode = _filter_modes_from_string.get(mode.lower(), None)
            coordinate_system = spatial_filter_like.get("coordinate_system", None)
            if isinstance(coordinate_system, str):
                coordinate_system = _coordinate_systems_from_string.get(coordinate_system.lower(), None)
            return SpatialFilter(
                geometry=spatial_filter_like["geometry"], mode=mode, coordinate_system=coordinate_system
            )

        raise ValueError(f"Invalid spatial filter: {spatial_filter_like}. Expected a shapely.Geometry or a dict.")


@dataclass(frozen=True)
class QueryFilters:
    temporal_extent: TimeInterval | IDInterval
    spatial_extent: SpatialFilter | None = None

    @classmethod
    def from_message(cls, filters: data_access_pb2.QueryFilters) -> "QueryFilters":
        temporal_extent: TimeInterval | IDInterval | None = None
        if filters.HasField("time_interval"):
            temporal_extent = TimeInterval.from_message(filters.time_interval)
        if filters.HasField("datapoint_interval"):
            temporal_extent = IDInterval.from_message(filters.datapoint_interval)

        if temporal_extent is None:
            raise ValueError("Invalid filter: time or datapoint interval must be set")

        spatial_extent = None
        if filters.HasField("spatial_extent"):
            spatial_extent = SpatialFilter.from_message(filters.spatial_extent)

        return QueryFilters(temporal_extent=temporal_extent, spatial_extent=spatial_extent)

    def to_message(self) -> data_access_pb2.QueryFilters:
        spatial_extent = self.spatial_extent.to_message() if self.spatial_extent else None
        if isinstance(self.temporal_extent, TimeInterval):
            return data_access_pb2.QueryFilters(
                time_interval=self.temporal_extent.to_message(), spatial_extent=spatial_extent
            )

        return data_access_pb2.QueryFilters(
            datapoint_interval=self.temporal_extent.to_message(), spatial_extent=spatial_extent
        )
