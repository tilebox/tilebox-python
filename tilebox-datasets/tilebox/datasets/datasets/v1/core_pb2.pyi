from tilebox.datasets.datasets.v1 import dataset_type_pb2 as _dataset_type_pb2
from tilebox.datasets.tilebox.v1 import id_pb2 as _id_pb2
from tilebox.datasets.tilebox.v1 import query_pb2 as _query_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class DatasetPermission(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    DATASET_PERMISSION_UNSPECIFIED: _ClassVar[DatasetPermission]
    DATASET_PERMISSION_ACCESS_DATA: _ClassVar[DatasetPermission]
    DATASET_PERMISSION_WRITE_DATA: _ClassVar[DatasetPermission]
    DATASET_PERMISSION_EDIT: _ClassVar[DatasetPermission]

class Visibility(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    VISIBILITY_UNSPECIFIED: _ClassVar[Visibility]
    VISIBILITY_PRIVATE: _ClassVar[Visibility]
    VISIBILITY_SHARED_WITH_ME: _ClassVar[Visibility]
    VISIBILITY_PUBLIC: _ClassVar[Visibility]
DATASET_PERMISSION_UNSPECIFIED: DatasetPermission
DATASET_PERMISSION_ACCESS_DATA: DatasetPermission
DATASET_PERMISSION_WRITE_DATA: DatasetPermission
DATASET_PERMISSION_EDIT: DatasetPermission
VISIBILITY_UNSPECIFIED: Visibility
VISIBILITY_PRIVATE: Visibility
VISIBILITY_SHARED_WITH_ME: Visibility
VISIBILITY_PUBLIC: Visibility

class Any(_message.Message):
    __slots__ = ("type_url", "value")
    TYPE_URL_FIELD_NUMBER: _ClassVar[int]
    VALUE_FIELD_NUMBER: _ClassVar[int]
    type_url: str
    value: bytes
    def __init__(self, type_url: _Optional[str] = ..., value: _Optional[bytes] = ...) -> None: ...

class RepeatedAny(_message.Message):
    __slots__ = ("type_url", "value")
    TYPE_URL_FIELD_NUMBER: _ClassVar[int]
    VALUE_FIELD_NUMBER: _ClassVar[int]
    type_url: str
    value: _containers.RepeatedScalarFieldContainer[bytes]
    def __init__(self, type_url: _Optional[str] = ..., value: _Optional[_Iterable[bytes]] = ...) -> None: ...

class Collection(_message.Message):
    __slots__ = ("name", "id")
    NAME_FIELD_NUMBER: _ClassVar[int]
    ID_FIELD_NUMBER: _ClassVar[int]
    name: str
    id: _id_pb2.ID
    def __init__(self, name: _Optional[str] = ..., id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ...) -> None: ...

class CollectionInfo(_message.Message):
    __slots__ = ("collection", "availability", "count")
    COLLECTION_FIELD_NUMBER: _ClassVar[int]
    AVAILABILITY_FIELD_NUMBER: _ClassVar[int]
    COUNT_FIELD_NUMBER: _ClassVar[int]
    collection: Collection
    availability: _query_pb2.TimeInterval
    count: int
    def __init__(self, collection: _Optional[_Union[Collection, _Mapping]] = ..., availability: _Optional[_Union[_query_pb2.TimeInterval, _Mapping]] = ..., count: _Optional[int] = ...) -> None: ...

class Dataset(_message.Message):
    __slots__ = ("id", "group_id", "type", "code_name", "name", "summary", "icon", "description", "permissions", "visibility", "slug", "type_editable", "collections")
    ID_FIELD_NUMBER: _ClassVar[int]
    GROUP_ID_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    CODE_NAME_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    SUMMARY_FIELD_NUMBER: _ClassVar[int]
    ICON_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    PERMISSIONS_FIELD_NUMBER: _ClassVar[int]
    VISIBILITY_FIELD_NUMBER: _ClassVar[int]
    SLUG_FIELD_NUMBER: _ClassVar[int]
    TYPE_EDITABLE_FIELD_NUMBER: _ClassVar[int]
    COLLECTIONS_FIELD_NUMBER: _ClassVar[int]
    id: _id_pb2.ID
    group_id: _id_pb2.ID
    type: _dataset_type_pb2.AnnotatedType
    code_name: str
    name: str
    summary: str
    icon: str
    description: str
    permissions: _containers.RepeatedScalarFieldContainer[DatasetPermission]
    visibility: Visibility
    slug: str
    type_editable: bool
    collections: _containers.RepeatedCompositeFieldContainer[CollectionInfo]
    def __init__(self, id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ..., group_id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ..., type: _Optional[_Union[_dataset_type_pb2.AnnotatedType, _Mapping]] = ..., code_name: _Optional[str] = ..., name: _Optional[str] = ..., summary: _Optional[str] = ..., icon: _Optional[str] = ..., description: _Optional[str] = ..., permissions: _Optional[_Iterable[_Union[DatasetPermission, str]]] = ..., visibility: _Optional[_Union[Visibility, str]] = ..., slug: _Optional[str] = ..., type_editable: bool = ..., collections: _Optional[_Iterable[_Union[CollectionInfo, _Mapping]]] = ...) -> None: ...

class DatasetGroup(_message.Message):
    __slots__ = ("id", "parent_id", "code_name", "name", "icon")
    ID_FIELD_NUMBER: _ClassVar[int]
    PARENT_ID_FIELD_NUMBER: _ClassVar[int]
    CODE_NAME_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    ICON_FIELD_NUMBER: _ClassVar[int]
    id: _id_pb2.ID
    parent_id: _id_pb2.ID
    code_name: str
    name: str
    icon: str
    def __init__(self, id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ..., parent_id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ..., code_name: _Optional[str] = ..., name: _Optional[str] = ..., icon: _Optional[str] = ...) -> None: ...
