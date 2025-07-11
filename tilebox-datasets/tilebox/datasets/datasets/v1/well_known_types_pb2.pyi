from google.protobuf import duration_pb2 as _duration_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Optional as _Optional

DESCRIPTOR: _descriptor.FileDescriptor

class FlightDirection(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    FLIGHT_DIRECTION_UNSPECIFIED: _ClassVar[FlightDirection]
    FLIGHT_DIRECTION_ASCENDING: _ClassVar[FlightDirection]
    FLIGHT_DIRECTION_DESCENDING: _ClassVar[FlightDirection]

class ObservationDirection(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    OBSERVATION_DIRECTION_UNSPECIFIED: _ClassVar[ObservationDirection]
    OBSERVATION_DIRECTION_LEFT: _ClassVar[ObservationDirection]
    OBSERVATION_DIRECTION_RIGHT: _ClassVar[ObservationDirection]

class OpendataProvider(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    OPENDATA_PROVIDER_UNSPECIFIED: _ClassVar[OpendataProvider]
    OPENDATA_PROVIDER_ASF: _ClassVar[OpendataProvider]
    OPENDATA_PROVIDER_COPERNICUS_DATASPACE: _ClassVar[OpendataProvider]
    OPENDATA_PROVIDER_UMBRA: _ClassVar[OpendataProvider]

class ProcessingLevel(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    PROCESSING_LEVEL_UNSPECIFIED: _ClassVar[ProcessingLevel]
    PROCESSING_LEVEL_L0: _ClassVar[ProcessingLevel]
    PROCESSING_LEVEL_L1: _ClassVar[ProcessingLevel]
    PROCESSING_LEVEL_L1A: _ClassVar[ProcessingLevel]
    PROCESSING_LEVEL_L1B: _ClassVar[ProcessingLevel]
    PROCESSING_LEVEL_L1C: _ClassVar[ProcessingLevel]
    PROCESSING_LEVEL_L2: _ClassVar[ProcessingLevel]
    PROCESSING_LEVEL_L2A: _ClassVar[ProcessingLevel]
    PROCESSING_LEVEL_L2B: _ClassVar[ProcessingLevel]
    PROCESSING_LEVEL_L3: _ClassVar[ProcessingLevel]
    PROCESSING_LEVEL_L3A: _ClassVar[ProcessingLevel]
    PROCESSING_LEVEL_L4: _ClassVar[ProcessingLevel]
    PROCESSING_LEVEL_NOT_APPLICABLE: _ClassVar[ProcessingLevel]

class Polarization(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    POLARIZATION_UNSPECIFIED: _ClassVar[Polarization]
    POLARIZATION_HH: _ClassVar[Polarization]
    POLARIZATION_HV: _ClassVar[Polarization]
    POLARIZATION_VH: _ClassVar[Polarization]
    POLARIZATION_VV: _ClassVar[Polarization]
    POLARIZATION_DUAL_HH: _ClassVar[Polarization]
    POLARIZATION_DUAL_HV: _ClassVar[Polarization]
    POLARIZATION_DUAL_VH: _ClassVar[Polarization]
    POLARIZATION_DUAL_VV: _ClassVar[Polarization]
    POLARIZATION_HH_HV: _ClassVar[Polarization]
    POLARIZATION_VV_VH: _ClassVar[Polarization]

class AcquisitionMode(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    ACQUISITION_MODE_UNSPECIFIED: _ClassVar[AcquisitionMode]
    ACQUISITION_MODE_SM: _ClassVar[AcquisitionMode]
    ACQUISITION_MODE_EW: _ClassVar[AcquisitionMode]
    ACQUISITION_MODE_IW: _ClassVar[AcquisitionMode]
    ACQUISITION_MODE_WV: _ClassVar[AcquisitionMode]
    ACQUISITION_MODE_SPOTLIGHT: _ClassVar[AcquisitionMode]
    ACQUISITION_MODE_NOBS: _ClassVar[AcquisitionMode]
    ACQUISITION_MODE_EOBS: _ClassVar[AcquisitionMode]
    ACQUISITION_MODE_DASC: _ClassVar[AcquisitionMode]
    ACQUISITION_MODE_ABSR: _ClassVar[AcquisitionMode]
    ACQUISITION_MODE_VIC: _ClassVar[AcquisitionMode]
    ACQUISITION_MODE_RAW: _ClassVar[AcquisitionMode]
    ACQUISITION_MODE_TST: _ClassVar[AcquisitionMode]
FLIGHT_DIRECTION_UNSPECIFIED: FlightDirection
FLIGHT_DIRECTION_ASCENDING: FlightDirection
FLIGHT_DIRECTION_DESCENDING: FlightDirection
OBSERVATION_DIRECTION_UNSPECIFIED: ObservationDirection
OBSERVATION_DIRECTION_LEFT: ObservationDirection
OBSERVATION_DIRECTION_RIGHT: ObservationDirection
OPENDATA_PROVIDER_UNSPECIFIED: OpendataProvider
OPENDATA_PROVIDER_ASF: OpendataProvider
OPENDATA_PROVIDER_COPERNICUS_DATASPACE: OpendataProvider
OPENDATA_PROVIDER_UMBRA: OpendataProvider
PROCESSING_LEVEL_UNSPECIFIED: ProcessingLevel
PROCESSING_LEVEL_L0: ProcessingLevel
PROCESSING_LEVEL_L1: ProcessingLevel
PROCESSING_LEVEL_L1A: ProcessingLevel
PROCESSING_LEVEL_L1B: ProcessingLevel
PROCESSING_LEVEL_L1C: ProcessingLevel
PROCESSING_LEVEL_L2: ProcessingLevel
PROCESSING_LEVEL_L2A: ProcessingLevel
PROCESSING_LEVEL_L2B: ProcessingLevel
PROCESSING_LEVEL_L3: ProcessingLevel
PROCESSING_LEVEL_L3A: ProcessingLevel
PROCESSING_LEVEL_L4: ProcessingLevel
PROCESSING_LEVEL_NOT_APPLICABLE: ProcessingLevel
POLARIZATION_UNSPECIFIED: Polarization
POLARIZATION_HH: Polarization
POLARIZATION_HV: Polarization
POLARIZATION_VH: Polarization
POLARIZATION_VV: Polarization
POLARIZATION_DUAL_HH: Polarization
POLARIZATION_DUAL_HV: Polarization
POLARIZATION_DUAL_VH: Polarization
POLARIZATION_DUAL_VV: Polarization
POLARIZATION_HH_HV: Polarization
POLARIZATION_VV_VH: Polarization
ACQUISITION_MODE_UNSPECIFIED: AcquisitionMode
ACQUISITION_MODE_SM: AcquisitionMode
ACQUISITION_MODE_EW: AcquisitionMode
ACQUISITION_MODE_IW: AcquisitionMode
ACQUISITION_MODE_WV: AcquisitionMode
ACQUISITION_MODE_SPOTLIGHT: AcquisitionMode
ACQUISITION_MODE_NOBS: AcquisitionMode
ACQUISITION_MODE_EOBS: AcquisitionMode
ACQUISITION_MODE_DASC: AcquisitionMode
ACQUISITION_MODE_ABSR: AcquisitionMode
ACQUISITION_MODE_VIC: AcquisitionMode
ACQUISITION_MODE_RAW: AcquisitionMode
ACQUISITION_MODE_TST: AcquisitionMode

class UUID(_message.Message):
    __slots__ = ("uuid",)
    UUID_FIELD_NUMBER: _ClassVar[int]
    uuid: bytes
    def __init__(self, uuid: _Optional[bytes] = ...) -> None: ...

class Vec3(_message.Message):
    __slots__ = ("x", "y", "z")
    X_FIELD_NUMBER: _ClassVar[int]
    Y_FIELD_NUMBER: _ClassVar[int]
    Z_FIELD_NUMBER: _ClassVar[int]
    x: float
    y: float
    z: float
    def __init__(self, x: _Optional[float] = ..., y: _Optional[float] = ..., z: _Optional[float] = ...) -> None: ...

class Quaternion(_message.Message):
    __slots__ = ("q1", "q2", "q3", "q4")
    Q1_FIELD_NUMBER: _ClassVar[int]
    Q2_FIELD_NUMBER: _ClassVar[int]
    Q3_FIELD_NUMBER: _ClassVar[int]
    Q4_FIELD_NUMBER: _ClassVar[int]
    q1: float
    q2: float
    q3: float
    q4: float
    def __init__(self, q1: _Optional[float] = ..., q2: _Optional[float] = ..., q3: _Optional[float] = ..., q4: _Optional[float] = ...) -> None: ...

class LatLon(_message.Message):
    __slots__ = ("latitude", "longitude")
    LATITUDE_FIELD_NUMBER: _ClassVar[int]
    LONGITUDE_FIELD_NUMBER: _ClassVar[int]
    latitude: float
    longitude: float
    def __init__(self, latitude: _Optional[float] = ..., longitude: _Optional[float] = ...) -> None: ...

class LatLonAlt(_message.Message):
    __slots__ = ("latitude", "longitude", "altitude")
    LATITUDE_FIELD_NUMBER: _ClassVar[int]
    LONGITUDE_FIELD_NUMBER: _ClassVar[int]
    ALTITUDE_FIELD_NUMBER: _ClassVar[int]
    latitude: float
    longitude: float
    altitude: float
    def __init__(self, latitude: _Optional[float] = ..., longitude: _Optional[float] = ..., altitude: _Optional[float] = ...) -> None: ...

class Geometry(_message.Message):
    __slots__ = ("wkb",)
    WKB_FIELD_NUMBER: _ClassVar[int]
    wkb: bytes
    def __init__(self, wkb: _Optional[bytes] = ...) -> None: ...
