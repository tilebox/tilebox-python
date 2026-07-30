"""Immutable models inspired by the STAC satellite extension.

See https://github.com/stac-extensions/sat.
"""

import datetime as dt
from dataclasses import dataclass

from tilebox.datasets.assets.converters import converters
from tilebox.datasets.datasets.stac.v1.satellite_pb2 import SatelliteOrbitStateVector as OrbitVectorProto
from tilebox.datasets.datasets.stac.v1.satellite_pb2 import SatelliteProperties as SatellitePropertiesProto


@converters.register(OrbitVectorProto)
@dataclass(frozen=True, slots=True)
class SatelliteOrbitStateVector:
    datetime: dt.datetime | None = None
    values: tuple[float, ...] = ()


@converters.register(SatellitePropertiesProto)
@dataclass(frozen=True, slots=True)
class SatelliteProperties:
    platform_international_designator: str | None = None
    orbit_state: str = "unspecified"
    absolute_orbit: int | None = None
    relative_orbit: int | None = None
    orbit_cycle: int | None = None
    orbit_state_vectors: tuple[SatelliteOrbitStateVector, ...] = ()
    anx_datetime: dt.datetime | None = None
    acquisition_station: str | None = None
