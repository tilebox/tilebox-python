from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class SARFrequencyBand(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    SAR_FREQUENCY_BAND_UNSPECIFIED: _ClassVar[SARFrequencyBand]
    SAR_FREQUENCY_BAND_P: _ClassVar[SARFrequencyBand]
    SAR_FREQUENCY_BAND_L: _ClassVar[SARFrequencyBand]
    SAR_FREQUENCY_BAND_S: _ClassVar[SARFrequencyBand]
    SAR_FREQUENCY_BAND_C: _ClassVar[SARFrequencyBand]
    SAR_FREQUENCY_BAND_X: _ClassVar[SARFrequencyBand]
    SAR_FREQUENCY_BAND_KU: _ClassVar[SARFrequencyBand]
    SAR_FREQUENCY_BAND_K: _ClassVar[SARFrequencyBand]
    SAR_FREQUENCY_BAND_KA: _ClassVar[SARFrequencyBand]

class SARPolarization(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    SAR_POLARIZATION_UNSPECIFIED: _ClassVar[SARPolarization]
    SAR_POLARIZATION_HH: _ClassVar[SARPolarization]
    SAR_POLARIZATION_VV: _ClassVar[SARPolarization]
    SAR_POLARIZATION_HV: _ClassVar[SARPolarization]
    SAR_POLARIZATION_VH: _ClassVar[SARPolarization]
    SAR_POLARIZATION_LH: _ClassVar[SARPolarization]
    SAR_POLARIZATION_LV: _ClassVar[SARPolarization]
    SAR_POLARIZATION_RH: _ClassVar[SARPolarization]
    SAR_POLARIZATION_RV: _ClassVar[SARPolarization]
    SAR_POLARIZATION_CH: _ClassVar[SARPolarization]
    SAR_POLARIZATION_CV: _ClassVar[SARPolarization]

class SARObservationDirection(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    SAR_OBSERVATION_DIRECTION_UNSPECIFIED: _ClassVar[SARObservationDirection]
    SAR_OBSERVATION_DIRECTION_LEFT: _ClassVar[SARObservationDirection]
    SAR_OBSERVATION_DIRECTION_RIGHT: _ClassVar[SARObservationDirection]
SAR_FREQUENCY_BAND_UNSPECIFIED: SARFrequencyBand
SAR_FREQUENCY_BAND_P: SARFrequencyBand
SAR_FREQUENCY_BAND_L: SARFrequencyBand
SAR_FREQUENCY_BAND_S: SARFrequencyBand
SAR_FREQUENCY_BAND_C: SARFrequencyBand
SAR_FREQUENCY_BAND_X: SARFrequencyBand
SAR_FREQUENCY_BAND_KU: SARFrequencyBand
SAR_FREQUENCY_BAND_K: SARFrequencyBand
SAR_FREQUENCY_BAND_KA: SARFrequencyBand
SAR_POLARIZATION_UNSPECIFIED: SARPolarization
SAR_POLARIZATION_HH: SARPolarization
SAR_POLARIZATION_VV: SARPolarization
SAR_POLARIZATION_HV: SARPolarization
SAR_POLARIZATION_VH: SARPolarization
SAR_POLARIZATION_LH: SARPolarization
SAR_POLARIZATION_LV: SARPolarization
SAR_POLARIZATION_RH: SARPolarization
SAR_POLARIZATION_RV: SARPolarization
SAR_POLARIZATION_CH: SARPolarization
SAR_POLARIZATION_CV: SARPolarization
SAR_OBSERVATION_DIRECTION_UNSPECIFIED: SARObservationDirection
SAR_OBSERVATION_DIRECTION_LEFT: SARObservationDirection
SAR_OBSERVATION_DIRECTION_RIGHT: SARObservationDirection

class SARProperties(_message.Message):
    __slots__ = ("polarizations", "instrument_mode", "frequency_band", "center_frequency", "bandwidth", "resolution_range", "resolution_azimuth", "pixel_spacing_range", "pixel_spacing_azimuth", "looks_range", "looks_azimuth", "looks_equivalent_number", "observation_direction", "relative_burst", "beam_ids")
    POLARIZATIONS_FIELD_NUMBER: _ClassVar[int]
    INSTRUMENT_MODE_FIELD_NUMBER: _ClassVar[int]
    FREQUENCY_BAND_FIELD_NUMBER: _ClassVar[int]
    CENTER_FREQUENCY_FIELD_NUMBER: _ClassVar[int]
    BANDWIDTH_FIELD_NUMBER: _ClassVar[int]
    RESOLUTION_RANGE_FIELD_NUMBER: _ClassVar[int]
    RESOLUTION_AZIMUTH_FIELD_NUMBER: _ClassVar[int]
    PIXEL_SPACING_RANGE_FIELD_NUMBER: _ClassVar[int]
    PIXEL_SPACING_AZIMUTH_FIELD_NUMBER: _ClassVar[int]
    LOOKS_RANGE_FIELD_NUMBER: _ClassVar[int]
    LOOKS_AZIMUTH_FIELD_NUMBER: _ClassVar[int]
    LOOKS_EQUIVALENT_NUMBER_FIELD_NUMBER: _ClassVar[int]
    OBSERVATION_DIRECTION_FIELD_NUMBER: _ClassVar[int]
    RELATIVE_BURST_FIELD_NUMBER: _ClassVar[int]
    BEAM_IDS_FIELD_NUMBER: _ClassVar[int]
    polarizations: _containers.RepeatedScalarFieldContainer[SARPolarization]
    instrument_mode: str
    frequency_band: SARFrequencyBand
    center_frequency: float
    bandwidth: float
    resolution_range: float
    resolution_azimuth: float
    pixel_spacing_range: float
    pixel_spacing_azimuth: float
    looks_range: int
    looks_azimuth: int
    looks_equivalent_number: float
    observation_direction: SARObservationDirection
    relative_burst: int
    beam_ids: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, polarizations: _Optional[_Iterable[_Union[SARPolarization, str]]] = ..., instrument_mode: _Optional[str] = ..., frequency_band: _Optional[_Union[SARFrequencyBand, str]] = ..., center_frequency: _Optional[float] = ..., bandwidth: _Optional[float] = ..., resolution_range: _Optional[float] = ..., resolution_azimuth: _Optional[float] = ..., pixel_spacing_range: _Optional[float] = ..., pixel_spacing_azimuth: _Optional[float] = ..., looks_range: _Optional[int] = ..., looks_azimuth: _Optional[int] = ..., looks_equivalent_number: _Optional[float] = ..., observation_direction: _Optional[_Union[SARObservationDirection, str]] = ..., relative_burst: _Optional[int] = ..., beam_ids: _Optional[_Iterable[str]] = ...) -> None: ...
