from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class KnownStorageType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    KNOWN_STORAGE_TYPE_UNSPECIFIED: _ClassVar[KnownStorageType]
    KNOWN_STORAGE_TYPE_AWS_S3: _ClassVar[KnownStorageType]
    KNOWN_STORAGE_TYPE_CUSTOM_S3: _ClassVar[KnownStorageType]
    KNOWN_STORAGE_TYPE_MICROSOFT_AZURE: _ClassVar[KnownStorageType]
    KNOWN_STORAGE_TYPE_GOOGLE_CLOUD_STORAGE: _ClassVar[KnownStorageType]
KNOWN_STORAGE_TYPE_UNSPECIFIED: KnownStorageType
KNOWN_STORAGE_TYPE_AWS_S3: KnownStorageType
KNOWN_STORAGE_TYPE_CUSTOM_S3: KnownStorageType
KNOWN_STORAGE_TYPE_MICROSOFT_AZURE: KnownStorageType
KNOWN_STORAGE_TYPE_GOOGLE_CLOUD_STORAGE: KnownStorageType

class Storage(_message.Message):
    __slots__ = ("schemes",)
    class SchemesEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: StorageScheme
        def __init__(self, key: _Optional[str] = ..., value: _Optional[_Union[StorageScheme, _Mapping]] = ...) -> None: ...
    SCHEMES_FIELD_NUMBER: _ClassVar[int]
    schemes: _containers.MessageMap[str, StorageScheme]
    def __init__(self, schemes: _Optional[_Mapping[str, StorageScheme]] = ...) -> None: ...

class StorageScheme(_message.Message):
    __slots__ = ("known_type", "custom_type", "platform", "title", "description", "region", "requester_pays", "storage_class")
    KNOWN_TYPE_FIELD_NUMBER: _ClassVar[int]
    CUSTOM_TYPE_FIELD_NUMBER: _ClassVar[int]
    PLATFORM_FIELD_NUMBER: _ClassVar[int]
    TITLE_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    REGION_FIELD_NUMBER: _ClassVar[int]
    REQUESTER_PAYS_FIELD_NUMBER: _ClassVar[int]
    STORAGE_CLASS_FIELD_NUMBER: _ClassVar[int]
    known_type: KnownStorageType
    custom_type: str
    platform: str
    title: str
    description: str
    region: str
    requester_pays: bool
    storage_class: str
    def __init__(self, known_type: _Optional[_Union[KnownStorageType, str]] = ..., custom_type: _Optional[str] = ..., platform: _Optional[str] = ..., title: _Optional[str] = ..., description: _Optional[str] = ..., region: _Optional[str] = ..., requester_pays: bool = ..., storage_class: _Optional[str] = ...) -> None: ...
