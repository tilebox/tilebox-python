from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class EOCommonName(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    EO_COMMON_NAME_UNSPECIFIED: _ClassVar[EOCommonName]
    EO_COMMON_NAME_PAN: _ClassVar[EOCommonName]
    EO_COMMON_NAME_COASTAL: _ClassVar[EOCommonName]
    EO_COMMON_NAME_BLUE: _ClassVar[EOCommonName]
    EO_COMMON_NAME_GREEN: _ClassVar[EOCommonName]
    EO_COMMON_NAME_GREEN05: _ClassVar[EOCommonName]
    EO_COMMON_NAME_YELLOW: _ClassVar[EOCommonName]
    EO_COMMON_NAME_RED: _ClassVar[EOCommonName]
    EO_COMMON_NAME_REDEDGE: _ClassVar[EOCommonName]
    EO_COMMON_NAME_REDEDGE071: _ClassVar[EOCommonName]
    EO_COMMON_NAME_REDEDGE075: _ClassVar[EOCommonName]
    EO_COMMON_NAME_REDEDGE078: _ClassVar[EOCommonName]
    EO_COMMON_NAME_NIR: _ClassVar[EOCommonName]
    EO_COMMON_NAME_NIR08: _ClassVar[EOCommonName]
    EO_COMMON_NAME_NIR09: _ClassVar[EOCommonName]
    EO_COMMON_NAME_CIRRUS: _ClassVar[EOCommonName]
    EO_COMMON_NAME_SWIR16: _ClassVar[EOCommonName]
    EO_COMMON_NAME_SWIR22: _ClassVar[EOCommonName]
    EO_COMMON_NAME_LWIR: _ClassVar[EOCommonName]
    EO_COMMON_NAME_LWIR11: _ClassVar[EOCommonName]
    EO_COMMON_NAME_LWIR12: _ClassVar[EOCommonName]

class RasterSampling(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    RASTER_SAMPLING_UNSPECIFIED: _ClassVar[RasterSampling]
    RASTER_SAMPLING_AREA: _ClassVar[RasterSampling]
    RASTER_SAMPLING_POINT: _ClassVar[RasterSampling]
EO_COMMON_NAME_UNSPECIFIED: EOCommonName
EO_COMMON_NAME_PAN: EOCommonName
EO_COMMON_NAME_COASTAL: EOCommonName
EO_COMMON_NAME_BLUE: EOCommonName
EO_COMMON_NAME_GREEN: EOCommonName
EO_COMMON_NAME_GREEN05: EOCommonName
EO_COMMON_NAME_YELLOW: EOCommonName
EO_COMMON_NAME_RED: EOCommonName
EO_COMMON_NAME_REDEDGE: EOCommonName
EO_COMMON_NAME_REDEDGE071: EOCommonName
EO_COMMON_NAME_REDEDGE075: EOCommonName
EO_COMMON_NAME_REDEDGE078: EOCommonName
EO_COMMON_NAME_NIR: EOCommonName
EO_COMMON_NAME_NIR08: EOCommonName
EO_COMMON_NAME_NIR09: EOCommonName
EO_COMMON_NAME_CIRRUS: EOCommonName
EO_COMMON_NAME_SWIR16: EOCommonName
EO_COMMON_NAME_SWIR22: EOCommonName
EO_COMMON_NAME_LWIR: EOCommonName
EO_COMMON_NAME_LWIR11: EOCommonName
EO_COMMON_NAME_LWIR12: EOCommonName
RASTER_SAMPLING_UNSPECIFIED: RasterSampling
RASTER_SAMPLING_AREA: RasterSampling
RASTER_SAMPLING_POINT: RasterSampling

class EOProperties(_message.Message):
    __slots__ = ("common_name", "center_wavelength", "full_width_half_max", "solar_illumination")
    COMMON_NAME_FIELD_NUMBER: _ClassVar[int]
    CENTER_WAVELENGTH_FIELD_NUMBER: _ClassVar[int]
    FULL_WIDTH_HALF_MAX_FIELD_NUMBER: _ClassVar[int]
    SOLAR_ILLUMINATION_FIELD_NUMBER: _ClassVar[int]
    common_name: EOCommonName
    center_wavelength: float
    full_width_half_max: float
    solar_illumination: float
    def __init__(self, common_name: _Optional[_Union[EOCommonName, str]] = ..., center_wavelength: _Optional[float] = ..., full_width_half_max: _Optional[float] = ..., solar_illumination: _Optional[float] = ...) -> None: ...

class RasterProperties(_message.Message):
    __slots__ = ("sampling", "scale", "offset", "spatial_resolution")
    SAMPLING_FIELD_NUMBER: _ClassVar[int]
    SCALE_FIELD_NUMBER: _ClassVar[int]
    OFFSET_FIELD_NUMBER: _ClassVar[int]
    SPATIAL_RESOLUTION_FIELD_NUMBER: _ClassVar[int]
    sampling: RasterSampling
    scale: float
    offset: float
    spatial_resolution: float
    def __init__(self, sampling: _Optional[_Union[RasterSampling, str]] = ..., scale: _Optional[float] = ..., offset: _Optional[float] = ..., spatial_resolution: _Optional[float] = ...) -> None: ...

class ClassificationClass(_message.Message):
    __slots__ = ("value", "description", "name", "title", "color_hint", "nodata", "percentage", "count")
    VALUE_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    TITLE_FIELD_NUMBER: _ClassVar[int]
    COLOR_HINT_FIELD_NUMBER: _ClassVar[int]
    NODATA_FIELD_NUMBER: _ClassVar[int]
    PERCENTAGE_FIELD_NUMBER: _ClassVar[int]
    COUNT_FIELD_NUMBER: _ClassVar[int]
    value: int
    description: str
    name: str
    title: str
    color_hint: str
    nodata: bool
    percentage: float
    count: int
    def __init__(self, value: _Optional[int] = ..., description: _Optional[str] = ..., name: _Optional[str] = ..., title: _Optional[str] = ..., color_hint: _Optional[str] = ..., nodata: bool = ..., percentage: _Optional[float] = ..., count: _Optional[int] = ...) -> None: ...

class Projection(_message.Message):
    __slots__ = ("code", "bbox", "shape", "transform")
    CODE_FIELD_NUMBER: _ClassVar[int]
    BBOX_FIELD_NUMBER: _ClassVar[int]
    SHAPE_FIELD_NUMBER: _ClassVar[int]
    TRANSFORM_FIELD_NUMBER: _ClassVar[int]
    code: str
    bbox: _containers.RepeatedScalarFieldContainer[float]
    shape: _containers.RepeatedScalarFieldContainer[int]
    transform: _containers.RepeatedScalarFieldContainer[float]
    def __init__(self, code: _Optional[str] = ..., bbox: _Optional[_Iterable[float]] = ..., shape: _Optional[_Iterable[int]] = ..., transform: _Optional[_Iterable[float]] = ...) -> None: ...

class View(_message.Message):
    __slots__ = ("incidence_angle", "azimuth")
    INCIDENCE_ANGLE_FIELD_NUMBER: _ClassVar[int]
    AZIMUTH_FIELD_NUMBER: _ClassVar[int]
    incidence_angle: float
    azimuth: float
    def __init__(self, incidence_angle: _Optional[float] = ..., azimuth: _Optional[float] = ...) -> None: ...

class File(_message.Message):
    __slots__ = ("checksum", "size", "local_path")
    CHECKSUM_FIELD_NUMBER: _ClassVar[int]
    SIZE_FIELD_NUMBER: _ClassVar[int]
    LOCAL_PATH_FIELD_NUMBER: _ClassVar[int]
    checksum: bytes
    size: int
    local_path: str
    def __init__(self, checksum: _Optional[bytes] = ..., size: _Optional[int] = ..., local_path: _Optional[str] = ...) -> None: ...
