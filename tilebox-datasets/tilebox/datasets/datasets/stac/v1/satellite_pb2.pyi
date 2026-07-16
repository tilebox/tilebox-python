from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class SatelliteOrbitState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    SATELLITE_ORBIT_STATE_UNSPECIFIED: _ClassVar[SatelliteOrbitState]
    SATELLITE_ORBIT_STATE_ASCENDING: _ClassVar[SatelliteOrbitState]
    SATELLITE_ORBIT_STATE_DESCENDING: _ClassVar[SatelliteOrbitState]
    SATELLITE_ORBIT_STATE_GEOSTATIONARY: _ClassVar[SatelliteOrbitState]
    SATELLITE_ORBIT_STATE_CROSSING: _ClassVar[SatelliteOrbitState]
SATELLITE_ORBIT_STATE_UNSPECIFIED: SatelliteOrbitState
SATELLITE_ORBIT_STATE_ASCENDING: SatelliteOrbitState
SATELLITE_ORBIT_STATE_DESCENDING: SatelliteOrbitState
SATELLITE_ORBIT_STATE_GEOSTATIONARY: SatelliteOrbitState
SATELLITE_ORBIT_STATE_CROSSING: SatelliteOrbitState

class SatelliteOrbitStateVector(_message.Message):
    __slots__ = ("datetime", "values")
    DATETIME_FIELD_NUMBER: _ClassVar[int]
    VALUES_FIELD_NUMBER: _ClassVar[int]
    datetime: _timestamp_pb2.Timestamp
    values: _containers.RepeatedScalarFieldContainer[float]
    def __init__(self, datetime: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., values: _Optional[_Iterable[float]] = ...) -> None: ...

class SatelliteProperties(_message.Message):
    __slots__ = ("platform_international_designator", "orbit_state", "absolute_orbit", "relative_orbit", "orbit_cycle", "orbit_state_vectors", "anx_datetime", "acquisition_station")
    PLATFORM_INTERNATIONAL_DESIGNATOR_FIELD_NUMBER: _ClassVar[int]
    ORBIT_STATE_FIELD_NUMBER: _ClassVar[int]
    ABSOLUTE_ORBIT_FIELD_NUMBER: _ClassVar[int]
    RELATIVE_ORBIT_FIELD_NUMBER: _ClassVar[int]
    ORBIT_CYCLE_FIELD_NUMBER: _ClassVar[int]
    ORBIT_STATE_VECTORS_FIELD_NUMBER: _ClassVar[int]
    ANX_DATETIME_FIELD_NUMBER: _ClassVar[int]
    ACQUISITION_STATION_FIELD_NUMBER: _ClassVar[int]
    platform_international_designator: str
    orbit_state: SatelliteOrbitState
    absolute_orbit: int
    relative_orbit: int
    orbit_cycle: int
    orbit_state_vectors: _containers.RepeatedCompositeFieldContainer[SatelliteOrbitStateVector]
    anx_datetime: _timestamp_pb2.Timestamp
    acquisition_station: str
    def __init__(self, platform_international_designator: _Optional[str] = ..., orbit_state: _Optional[_Union[SatelliteOrbitState, str]] = ..., absolute_orbit: _Optional[int] = ..., relative_orbit: _Optional[int] = ..., orbit_cycle: _Optional[int] = ..., orbit_state_vectors: _Optional[_Iterable[_Union[SatelliteOrbitStateVector, _Mapping]]] = ..., anx_datetime: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., acquisition_station: _Optional[str] = ...) -> None: ...
