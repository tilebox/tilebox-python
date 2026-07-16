from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class KnownMediaType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    KNOWN_MEDIA_TYPE_UNSPECIFIED: _ClassVar[KnownMediaType]
    KNOWN_MEDIA_TYPE_GEOJSON: _ClassVar[KnownMediaType]
    KNOWN_MEDIA_TYPE_JSON: _ClassVar[KnownMediaType]
    KNOWN_MEDIA_TYPE_CLOUD_OPTIMIZED_GEOTIFF: _ClassVar[KnownMediaType]
    KNOWN_MEDIA_TYPE_JPEG_2000: _ClassVar[KnownMediaType]
    KNOWN_MEDIA_TYPE_JPEG: _ClassVar[KnownMediaType]
    KNOWN_MEDIA_TYPE_PNG: _ClassVar[KnownMediaType]
    KNOWN_MEDIA_TYPE_APPLICATION_XML: _ClassVar[KnownMediaType]
    KNOWN_MEDIA_TYPE_ZIP: _ClassVar[KnownMediaType]
    KNOWN_MEDIA_TYPE_DIRECTORY: _ClassVar[KnownMediaType]
    KNOWN_MEDIA_TYPE_GEOTIFF: _ClassVar[KnownMediaType]
    KNOWN_MEDIA_TYPE_TIFF: _ClassVar[KnownMediaType]
    KNOWN_MEDIA_TYPE_HDF5: _ClassVar[KnownMediaType]
    KNOWN_MEDIA_TYPE_HDF: _ClassVar[KnownMediaType]
    KNOWN_MEDIA_TYPE_NETCDF: _ClassVar[KnownMediaType]
    KNOWN_MEDIA_TYPE_ZARR_V2: _ClassVar[KnownMediaType]
    KNOWN_MEDIA_TYPE_ZARR_V3: _ClassVar[KnownMediaType]
    KNOWN_MEDIA_TYPE_PARQUET: _ClassVar[KnownMediaType]
    KNOWN_MEDIA_TYPE_GEOPACKAGE: _ClassVar[KnownMediaType]
    KNOWN_MEDIA_TYPE_COPC: _ClassVar[KnownMediaType]
    KNOWN_MEDIA_TYPE_HTML: _ClassVar[KnownMediaType]
    KNOWN_MEDIA_TYPE_TEXT: _ClassVar[KnownMediaType]
    KNOWN_MEDIA_TYPE_TEXT_XML: _ClassVar[KnownMediaType]
    KNOWN_MEDIA_TYPE_FLATGEOBUF: _ClassVar[KnownMediaType]
    KNOWN_MEDIA_TYPE_PMTILES: _ClassVar[KnownMediaType]
    KNOWN_MEDIA_TYPE_NITF: _ClassVar[KnownMediaType]
    KNOWN_MEDIA_TYPE_OCTET_STREAM: _ClassVar[KnownMediaType]

class ProviderRole(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    PROVIDER_ROLE_UNSPECIFIED: _ClassVar[ProviderRole]
    PROVIDER_ROLE_PRODUCER: _ClassVar[ProviderRole]
    PROVIDER_ROLE_LICENSOR: _ClassVar[ProviderRole]
    PROVIDER_ROLE_PROCESSOR: _ClassVar[ProviderRole]
    PROVIDER_ROLE_HOST: _ClassVar[ProviderRole]
KNOWN_MEDIA_TYPE_UNSPECIFIED: KnownMediaType
KNOWN_MEDIA_TYPE_GEOJSON: KnownMediaType
KNOWN_MEDIA_TYPE_JSON: KnownMediaType
KNOWN_MEDIA_TYPE_CLOUD_OPTIMIZED_GEOTIFF: KnownMediaType
KNOWN_MEDIA_TYPE_JPEG_2000: KnownMediaType
KNOWN_MEDIA_TYPE_JPEG: KnownMediaType
KNOWN_MEDIA_TYPE_PNG: KnownMediaType
KNOWN_MEDIA_TYPE_APPLICATION_XML: KnownMediaType
KNOWN_MEDIA_TYPE_ZIP: KnownMediaType
KNOWN_MEDIA_TYPE_DIRECTORY: KnownMediaType
KNOWN_MEDIA_TYPE_GEOTIFF: KnownMediaType
KNOWN_MEDIA_TYPE_TIFF: KnownMediaType
KNOWN_MEDIA_TYPE_HDF5: KnownMediaType
KNOWN_MEDIA_TYPE_HDF: KnownMediaType
KNOWN_MEDIA_TYPE_NETCDF: KnownMediaType
KNOWN_MEDIA_TYPE_ZARR_V2: KnownMediaType
KNOWN_MEDIA_TYPE_ZARR_V3: KnownMediaType
KNOWN_MEDIA_TYPE_PARQUET: KnownMediaType
KNOWN_MEDIA_TYPE_GEOPACKAGE: KnownMediaType
KNOWN_MEDIA_TYPE_COPC: KnownMediaType
KNOWN_MEDIA_TYPE_HTML: KnownMediaType
KNOWN_MEDIA_TYPE_TEXT: KnownMediaType
KNOWN_MEDIA_TYPE_TEXT_XML: KnownMediaType
KNOWN_MEDIA_TYPE_FLATGEOBUF: KnownMediaType
KNOWN_MEDIA_TYPE_PMTILES: KnownMediaType
KNOWN_MEDIA_TYPE_NITF: KnownMediaType
KNOWN_MEDIA_TYPE_OCTET_STREAM: KnownMediaType
PROVIDER_ROLE_UNSPECIFIED: ProviderRole
PROVIDER_ROLE_PRODUCER: ProviderRole
PROVIDER_ROLE_LICENSOR: ProviderRole
PROVIDER_ROLE_PROCESSOR: ProviderRole
PROVIDER_ROLE_HOST: ProviderRole

class MediaType(_message.Message):
    __slots__ = ("known", "custom")
    KNOWN_FIELD_NUMBER: _ClassVar[int]
    CUSTOM_FIELD_NUMBER: _ClassVar[int]
    known: KnownMediaType
    custom: str
    def __init__(self, known: _Optional[_Union[KnownMediaType, str]] = ..., custom: _Optional[str] = ...) -> None: ...

class Provider(_message.Message):
    __slots__ = ("name", "description", "roles", "url")
    NAME_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    ROLES_FIELD_NUMBER: _ClassVar[int]
    URL_FIELD_NUMBER: _ClassVar[int]
    name: str
    description: str
    roles: _containers.RepeatedScalarFieldContainer[ProviderRole]
    url: str
    def __init__(self, name: _Optional[str] = ..., description: _Optional[str] = ..., roles: _Optional[_Iterable[_Union[ProviderRole, str]]] = ..., url: _Optional[str] = ...) -> None: ...

class Link(_message.Message):
    __slots__ = ("href", "rel", "media_type", "title", "storage_refs", "auth_refs")
    HREF_FIELD_NUMBER: _ClassVar[int]
    REL_FIELD_NUMBER: _ClassVar[int]
    MEDIA_TYPE_FIELD_NUMBER: _ClassVar[int]
    TITLE_FIELD_NUMBER: _ClassVar[int]
    STORAGE_REFS_FIELD_NUMBER: _ClassVar[int]
    AUTH_REFS_FIELD_NUMBER: _ClassVar[int]
    href: str
    rel: str
    media_type: MediaType
    title: str
    storage_refs: _containers.RepeatedScalarFieldContainer[str]
    auth_refs: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, href: _Optional[str] = ..., rel: _Optional[str] = ..., media_type: _Optional[_Union[MediaType, _Mapping]] = ..., title: _Optional[str] = ..., storage_refs: _Optional[_Iterable[str]] = ..., auth_refs: _Optional[_Iterable[str]] = ...) -> None: ...

class Links(_message.Message):
    __slots__ = ("links",)
    LINKS_FIELD_NUMBER: _ClassVar[int]
    links: _containers.RepeatedCompositeFieldContainer[Link]
    def __init__(self, links: _Optional[_Iterable[_Union[Link, _Mapping]]] = ...) -> None: ...
