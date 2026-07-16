from tilebox.datasets.datasets.stac.v1 import asset_metadata_pb2 as _asset_metadata_pb2
from tilebox.datasets.datasets.stac.v1 import core_pb2 as _core_pb2
from tilebox.datasets.datasets.stac.v1 import product_pb2 as _product_pb2
from tilebox.datasets.datasets.stac.v1 import sar_pb2 as _sar_pb2
from tilebox.datasets.datasets.stac.v1 import satellite_pb2 as _satellite_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class KnownAssetRole(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    KNOWN_ASSET_ROLE_UNSPECIFIED: _ClassVar[KnownAssetRole]
    KNOWN_ASSET_ROLE_DATA: _ClassVar[KnownAssetRole]
    KNOWN_ASSET_ROLE_METADATA: _ClassVar[KnownAssetRole]
    KNOWN_ASSET_ROLE_THUMBNAIL: _ClassVar[KnownAssetRole]
    KNOWN_ASSET_ROLE_OVERVIEW: _ClassVar[KnownAssetRole]
    KNOWN_ASSET_ROLE_VISUAL: _ClassVar[KnownAssetRole]
    KNOWN_ASSET_ROLE_DATE: _ClassVar[KnownAssetRole]
    KNOWN_ASSET_ROLE_GRAPHIC: _ClassVar[KnownAssetRole]
    KNOWN_ASSET_ROLE_DATA_MASK: _ClassVar[KnownAssetRole]
    KNOWN_ASSET_ROLE_SNOW_ICE: _ClassVar[KnownAssetRole]
    KNOWN_ASSET_ROLE_LAND_WATER: _ClassVar[KnownAssetRole]
    KNOWN_ASSET_ROLE_WATER_MASK: _ClassVar[KnownAssetRole]
    KNOWN_ASSET_ROLE_ISO_19115: _ClassVar[KnownAssetRole]
    KNOWN_ASSET_ROLE_REFLECTANCE: _ClassVar[KnownAssetRole]
    KNOWN_ASSET_ROLE_TEMPERATURE: _ClassVar[KnownAssetRole]
    KNOWN_ASSET_ROLE_SATURATION: _ClassVar[KnownAssetRole]
    KNOWN_ASSET_ROLE_CLOUD: _ClassVar[KnownAssetRole]
    KNOWN_ASSET_ROLE_CLOUD_SHADOW: _ClassVar[KnownAssetRole]
    KNOWN_ASSET_ROLE_LOCAL_INCIDENCE_ANGLE: _ClassVar[KnownAssetRole]
    KNOWN_ASSET_ROLE_ELLIPSOID_INCIDENCE_ANGLE: _ClassVar[KnownAssetRole]
    KNOWN_ASSET_ROLE_NOISE_POWER: _ClassVar[KnownAssetRole]
    KNOWN_ASSET_ROLE_AMPLITUDE: _ClassVar[KnownAssetRole]
    KNOWN_ASSET_ROLE_MAGNITUDE: _ClassVar[KnownAssetRole]
    KNOWN_ASSET_ROLE_SIGMA0: _ClassVar[KnownAssetRole]
    KNOWN_ASSET_ROLE_BETA0: _ClassVar[KnownAssetRole]
    KNOWN_ASSET_ROLE_GAMMA0: _ClassVar[KnownAssetRole]
    KNOWN_ASSET_ROLE_DATE_OFFSET: _ClassVar[KnownAssetRole]
    KNOWN_ASSET_ROLE_COVMAT: _ClassVar[KnownAssetRole]
    KNOWN_ASSET_ROLE_PRD: _ClassVar[KnownAssetRole]

class DataType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    DATA_TYPE_UNSPECIFIED: _ClassVar[DataType]
    DATA_TYPE_INT8: _ClassVar[DataType]
    DATA_TYPE_INT16: _ClassVar[DataType]
    DATA_TYPE_INT32: _ClassVar[DataType]
    DATA_TYPE_INT64: _ClassVar[DataType]
    DATA_TYPE_UINT8: _ClassVar[DataType]
    DATA_TYPE_UINT16: _ClassVar[DataType]
    DATA_TYPE_UINT32: _ClassVar[DataType]
    DATA_TYPE_UINT64: _ClassVar[DataType]
    DATA_TYPE_FLOAT16: _ClassVar[DataType]
    DATA_TYPE_FLOAT32: _ClassVar[DataType]
    DATA_TYPE_FLOAT64: _ClassVar[DataType]
    DATA_TYPE_CINT16: _ClassVar[DataType]
    DATA_TYPE_CINT32: _ClassVar[DataType]
    DATA_TYPE_CFLOAT32: _ClassVar[DataType]
    DATA_TYPE_CFLOAT64: _ClassVar[DataType]
    DATA_TYPE_OTHER: _ClassVar[DataType]
KNOWN_ASSET_ROLE_UNSPECIFIED: KnownAssetRole
KNOWN_ASSET_ROLE_DATA: KnownAssetRole
KNOWN_ASSET_ROLE_METADATA: KnownAssetRole
KNOWN_ASSET_ROLE_THUMBNAIL: KnownAssetRole
KNOWN_ASSET_ROLE_OVERVIEW: KnownAssetRole
KNOWN_ASSET_ROLE_VISUAL: KnownAssetRole
KNOWN_ASSET_ROLE_DATE: KnownAssetRole
KNOWN_ASSET_ROLE_GRAPHIC: KnownAssetRole
KNOWN_ASSET_ROLE_DATA_MASK: KnownAssetRole
KNOWN_ASSET_ROLE_SNOW_ICE: KnownAssetRole
KNOWN_ASSET_ROLE_LAND_WATER: KnownAssetRole
KNOWN_ASSET_ROLE_WATER_MASK: KnownAssetRole
KNOWN_ASSET_ROLE_ISO_19115: KnownAssetRole
KNOWN_ASSET_ROLE_REFLECTANCE: KnownAssetRole
KNOWN_ASSET_ROLE_TEMPERATURE: KnownAssetRole
KNOWN_ASSET_ROLE_SATURATION: KnownAssetRole
KNOWN_ASSET_ROLE_CLOUD: KnownAssetRole
KNOWN_ASSET_ROLE_CLOUD_SHADOW: KnownAssetRole
KNOWN_ASSET_ROLE_LOCAL_INCIDENCE_ANGLE: KnownAssetRole
KNOWN_ASSET_ROLE_ELLIPSOID_INCIDENCE_ANGLE: KnownAssetRole
KNOWN_ASSET_ROLE_NOISE_POWER: KnownAssetRole
KNOWN_ASSET_ROLE_AMPLITUDE: KnownAssetRole
KNOWN_ASSET_ROLE_MAGNITUDE: KnownAssetRole
KNOWN_ASSET_ROLE_SIGMA0: KnownAssetRole
KNOWN_ASSET_ROLE_BETA0: KnownAssetRole
KNOWN_ASSET_ROLE_GAMMA0: KnownAssetRole
KNOWN_ASSET_ROLE_DATE_OFFSET: KnownAssetRole
KNOWN_ASSET_ROLE_COVMAT: KnownAssetRole
KNOWN_ASSET_ROLE_PRD: KnownAssetRole
DATA_TYPE_UNSPECIFIED: DataType
DATA_TYPE_INT8: DataType
DATA_TYPE_INT16: DataType
DATA_TYPE_INT32: DataType
DATA_TYPE_INT64: DataType
DATA_TYPE_UINT8: DataType
DATA_TYPE_UINT16: DataType
DATA_TYPE_UINT32: DataType
DATA_TYPE_UINT64: DataType
DATA_TYPE_FLOAT16: DataType
DATA_TYPE_FLOAT32: DataType
DATA_TYPE_FLOAT64: DataType
DATA_TYPE_CINT16: DataType
DATA_TYPE_CINT32: DataType
DATA_TYPE_CFLOAT32: DataType
DATA_TYPE_CFLOAT64: DataType
DATA_TYPE_OTHER: DataType

class Statistics(_message.Message):
    __slots__ = ("minimum", "maximum")
    MINIMUM_FIELD_NUMBER: _ClassVar[int]
    MAXIMUM_FIELD_NUMBER: _ClassVar[int]
    minimum: float
    maximum: float
    def __init__(self, minimum: _Optional[float] = ..., maximum: _Optional[float] = ...) -> None: ...

class AssetAccessProfile(_message.Message):
    __slots__ = ("alternate_key", "default_alternate_name", "base_href", "storage_refs", "auth_refs")
    ALTERNATE_KEY_FIELD_NUMBER: _ClassVar[int]
    DEFAULT_ALTERNATE_NAME_FIELD_NUMBER: _ClassVar[int]
    BASE_HREF_FIELD_NUMBER: _ClassVar[int]
    STORAGE_REFS_FIELD_NUMBER: _ClassVar[int]
    AUTH_REFS_FIELD_NUMBER: _ClassVar[int]
    alternate_key: str
    default_alternate_name: str
    base_href: str
    storage_refs: _containers.RepeatedScalarFieldContainer[str]
    auth_refs: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, alternate_key: _Optional[str] = ..., default_alternate_name: _Optional[str] = ..., base_href: _Optional[str] = ..., storage_refs: _Optional[_Iterable[str]] = ..., auth_refs: _Optional[_Iterable[str]] = ...) -> None: ...

class AssetLocation(_message.Message):
    __slots__ = ("access_profile_index", "href", "alternate_name")
    ACCESS_PROFILE_INDEX_FIELD_NUMBER: _ClassVar[int]
    HREF_FIELD_NUMBER: _ClassVar[int]
    ALTERNATE_NAME_FIELD_NUMBER: _ClassVar[int]
    access_profile_index: int
    href: str
    alternate_name: str
    def __init__(self, access_profile_index: _Optional[int] = ..., href: _Optional[str] = ..., alternate_name: _Optional[str] = ...) -> None: ...

class Band(_message.Message):
    __slots__ = ("name", "description", "data_type", "nodata", "unit", "eo", "raster", "classes", "sar")
    NAME_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    DATA_TYPE_FIELD_NUMBER: _ClassVar[int]
    NODATA_FIELD_NUMBER: _ClassVar[int]
    UNIT_FIELD_NUMBER: _ClassVar[int]
    EO_FIELD_NUMBER: _ClassVar[int]
    RASTER_FIELD_NUMBER: _ClassVar[int]
    CLASSES_FIELD_NUMBER: _ClassVar[int]
    SAR_FIELD_NUMBER: _ClassVar[int]
    name: str
    description: str
    data_type: DataType
    nodata: float
    unit: str
    eo: _asset_metadata_pb2.EOProperties
    raster: _asset_metadata_pb2.RasterProperties
    classes: _containers.RepeatedCompositeFieldContainer[_asset_metadata_pb2.ClassificationClass]
    sar: _sar_pb2.SARProperties
    def __init__(self, name: _Optional[str] = ..., description: _Optional[str] = ..., data_type: _Optional[_Union[DataType, str]] = ..., nodata: _Optional[float] = ..., unit: _Optional[str] = ..., eo: _Optional[_Union[_asset_metadata_pb2.EOProperties, _Mapping]] = ..., raster: _Optional[_Union[_asset_metadata_pb2.RasterProperties, _Mapping]] = ..., classes: _Optional[_Iterable[_Union[_asset_metadata_pb2.ClassificationClass, _Mapping]]] = ..., sar: _Optional[_Union[_sar_pb2.SARProperties, _Mapping]] = ...) -> None: ...

class Asset(_message.Message):
    __slots__ = ("key", "primary", "alternates", "media_type", "title", "description", "roles", "custom_roles", "gsd", "band_profile_indices", "data_type", "nodata", "statistics", "unit", "eo", "raster", "projection", "view", "classes", "file", "sar", "satellite", "product")
    KEY_FIELD_NUMBER: _ClassVar[int]
    PRIMARY_FIELD_NUMBER: _ClassVar[int]
    ALTERNATES_FIELD_NUMBER: _ClassVar[int]
    MEDIA_TYPE_FIELD_NUMBER: _ClassVar[int]
    TITLE_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    ROLES_FIELD_NUMBER: _ClassVar[int]
    CUSTOM_ROLES_FIELD_NUMBER: _ClassVar[int]
    GSD_FIELD_NUMBER: _ClassVar[int]
    BAND_PROFILE_INDICES_FIELD_NUMBER: _ClassVar[int]
    DATA_TYPE_FIELD_NUMBER: _ClassVar[int]
    NODATA_FIELD_NUMBER: _ClassVar[int]
    STATISTICS_FIELD_NUMBER: _ClassVar[int]
    UNIT_FIELD_NUMBER: _ClassVar[int]
    EO_FIELD_NUMBER: _ClassVar[int]
    RASTER_FIELD_NUMBER: _ClassVar[int]
    PROJECTION_FIELD_NUMBER: _ClassVar[int]
    VIEW_FIELD_NUMBER: _ClassVar[int]
    CLASSES_FIELD_NUMBER: _ClassVar[int]
    FILE_FIELD_NUMBER: _ClassVar[int]
    SAR_FIELD_NUMBER: _ClassVar[int]
    SATELLITE_FIELD_NUMBER: _ClassVar[int]
    PRODUCT_FIELD_NUMBER: _ClassVar[int]
    key: str
    primary: AssetLocation
    alternates: _containers.RepeatedCompositeFieldContainer[AssetLocation]
    media_type: _core_pb2.MediaType
    title: str
    description: str
    roles: _containers.RepeatedScalarFieldContainer[KnownAssetRole]
    custom_roles: _containers.RepeatedScalarFieldContainer[str]
    gsd: float
    band_profile_indices: _containers.RepeatedScalarFieldContainer[int]
    data_type: DataType
    nodata: float
    statistics: Statistics
    unit: str
    eo: _asset_metadata_pb2.EOProperties
    raster: _asset_metadata_pb2.RasterProperties
    projection: _asset_metadata_pb2.Projection
    view: _asset_metadata_pb2.View
    classes: _containers.RepeatedCompositeFieldContainer[_asset_metadata_pb2.ClassificationClass]
    file: _asset_metadata_pb2.File
    sar: _sar_pb2.SARProperties
    satellite: _satellite_pb2.SatelliteProperties
    product: _product_pb2.ProductProperties
    def __init__(self, key: _Optional[str] = ..., primary: _Optional[_Union[AssetLocation, _Mapping]] = ..., alternates: _Optional[_Iterable[_Union[AssetLocation, _Mapping]]] = ..., media_type: _Optional[_Union[_core_pb2.MediaType, _Mapping]] = ..., title: _Optional[str] = ..., description: _Optional[str] = ..., roles: _Optional[_Iterable[_Union[KnownAssetRole, str]]] = ..., custom_roles: _Optional[_Iterable[str]] = ..., gsd: _Optional[float] = ..., band_profile_indices: _Optional[_Iterable[int]] = ..., data_type: _Optional[_Union[DataType, str]] = ..., nodata: _Optional[float] = ..., statistics: _Optional[_Union[Statistics, _Mapping]] = ..., unit: _Optional[str] = ..., eo: _Optional[_Union[_asset_metadata_pb2.EOProperties, _Mapping]] = ..., raster: _Optional[_Union[_asset_metadata_pb2.RasterProperties, _Mapping]] = ..., projection: _Optional[_Union[_asset_metadata_pb2.Projection, _Mapping]] = ..., view: _Optional[_Union[_asset_metadata_pb2.View, _Mapping]] = ..., classes: _Optional[_Iterable[_Union[_asset_metadata_pb2.ClassificationClass, _Mapping]]] = ..., file: _Optional[_Union[_asset_metadata_pb2.File, _Mapping]] = ..., sar: _Optional[_Union[_sar_pb2.SARProperties, _Mapping]] = ..., satellite: _Optional[_Union[_satellite_pb2.SatelliteProperties, _Mapping]] = ..., product: _Optional[_Union[_product_pb2.ProductProperties, _Mapping]] = ...) -> None: ...

class Assets(_message.Message):
    __slots__ = ("access_profiles", "band_profiles", "assets")
    ACCESS_PROFILES_FIELD_NUMBER: _ClassVar[int]
    BAND_PROFILES_FIELD_NUMBER: _ClassVar[int]
    ASSETS_FIELD_NUMBER: _ClassVar[int]
    access_profiles: _containers.RepeatedCompositeFieldContainer[AssetAccessProfile]
    band_profiles: _containers.RepeatedCompositeFieldContainer[Band]
    assets: _containers.RepeatedCompositeFieldContainer[Asset]
    def __init__(self, access_profiles: _Optional[_Iterable[_Union[AssetAccessProfile, _Mapping]]] = ..., band_profiles: _Optional[_Iterable[_Union[Band, _Mapping]]] = ..., assets: _Optional[_Iterable[_Union[Asset, _Mapping]]] = ...) -> None: ...
