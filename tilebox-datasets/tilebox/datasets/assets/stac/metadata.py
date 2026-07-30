"""Immutable models inspired by STAC asset, EO, raster, projection, view, classification, and file metadata specs.

See https://github.com/radiantearth/stac-spec and https://stac-extensions.github.io/.
"""

from dataclasses import dataclass

from tilebox.datasets.assets.converters import converters
from tilebox.datasets.datasets.stac.v1.asset_metadata_pb2 import (
    ClassificationClass as ClassificationClassProto,
)
from tilebox.datasets.datasets.stac.v1.asset_metadata_pb2 import EOProperties as EOPropertiesProto
from tilebox.datasets.datasets.stac.v1.asset_metadata_pb2 import File as FileProto
from tilebox.datasets.datasets.stac.v1.asset_metadata_pb2 import Projection as ProjectionProto
from tilebox.datasets.datasets.stac.v1.asset_metadata_pb2 import RasterProperties as RasterPropertiesProto
from tilebox.datasets.datasets.stac.v1.asset_metadata_pb2 import View as ViewProto
from tilebox.datasets.datasets.stac.v1.asset_pb2 import Statistics as StatisticsProto


@converters.register(StatisticsProto)
@dataclass(frozen=True, slots=True)
class Statistics:
    minimum: float | None = None
    maximum: float | None = None


@converters.register(EOPropertiesProto)
@dataclass(frozen=True, slots=True)
class ElectroOpticalProperties:
    common_name: str = "unspecified"
    center_wavelength: float | None = None
    full_width_half_max: float | None = None
    solar_illumination: float | None = None


@converters.register(RasterPropertiesProto)
@dataclass(frozen=True, slots=True)
class RasterProperties:
    sampling: str = "unspecified"
    scale: float | None = None
    offset: float | None = None
    spatial_resolution: float | None = None


@converters.register(ClassificationClassProto)
@dataclass(frozen=True, slots=True)
class ClassificationClass:
    value: int | None = None
    description: str | None = None
    name: str | None = None
    title: str | None = None
    color_hint: str | None = None
    nodata: bool | None = None
    percentage: float | None = None
    count: int | None = None


@converters.register(ProjectionProto)
@dataclass(frozen=True, slots=True)
class Projection:
    # STAC permits 2D/3D bboxes and six- or nine-element affine transforms.
    bbox: tuple[float, ...] = ()
    shape: tuple[int, ...] = ()
    transform: tuple[float, ...] = ()
    code: str | None = None


@converters.register(ViewProto)
@dataclass(frozen=True, slots=True)
class View:
    incidence_angle: float | None = None
    azimuth: float | None = None


@converters.register(FileProto)
@dataclass(frozen=True, slots=True)
class File:
    checksum: bytes | None = None
    size: int | None = None
    local_path: str | None = None
