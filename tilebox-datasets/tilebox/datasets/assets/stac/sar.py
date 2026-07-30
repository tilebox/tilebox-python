"""Immutable model inspired by the STAC SAR extension.

See https://github.com/stac-extensions/sar.
"""

from dataclasses import dataclass

from tilebox.datasets.assets.converters import converters
from tilebox.datasets.datasets.stac.v1.sar_pb2 import SARProperties as SARPropertiesProto


@converters.register(SARPropertiesProto)
@dataclass(frozen=True, slots=True)
class SarProperties:
    polarizations: tuple[str, ...] = ()
    instrument_mode: str | None = None
    frequency_band: str = "unspecified"
    center_frequency: float | None = None
    bandwidth: float | None = None
    resolution_range: float | None = None
    resolution_azimuth: float | None = None
    pixel_spacing_range: float | None = None
    pixel_spacing_azimuth: float | None = None
    looks_range: int | None = None
    looks_azimuth: int | None = None
    looks_equivalent_number: float | None = None
    observation_direction: str = "unspecified"
    relative_burst: int | None = None
    beam_ids: tuple[str, ...] = ()
