from tilebox.datasets.datasets.v1 import core_pb2 as _core_pb2
from tilebox.datasets.tilebox.v1 import id_pb2 as _id_pb2
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class CreateCollectionRequest(_message.Message):
    __slots__ = ("dataset_id", "name")
    DATASET_ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    dataset_id: _id_pb2.ID
    name: str
    def __init__(self, dataset_id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ..., name: _Optional[str] = ...) -> None: ...

class GetCollectionByNameRequest(_message.Message):
    __slots__ = ("collection_name", "with_availability", "with_count", "dataset_id")
    COLLECTION_NAME_FIELD_NUMBER: _ClassVar[int]
    WITH_AVAILABILITY_FIELD_NUMBER: _ClassVar[int]
    WITH_COUNT_FIELD_NUMBER: _ClassVar[int]
    DATASET_ID_FIELD_NUMBER: _ClassVar[int]
    collection_name: str
    with_availability: bool
    with_count: bool
    dataset_id: _id_pb2.ID
    def __init__(self, collection_name: _Optional[str] = ..., with_availability: bool = ..., with_count: bool = ..., dataset_id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ...) -> None: ...

class DeleteCollectionRequest(_message.Message):
    __slots__ = ("collection_id", "dataset_id")
    COLLECTION_ID_FIELD_NUMBER: _ClassVar[int]
    DATASET_ID_FIELD_NUMBER: _ClassVar[int]
    collection_id: _id_pb2.ID
    dataset_id: _id_pb2.ID
    def __init__(self, collection_id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ..., dataset_id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ...) -> None: ...

class DeleteCollectionResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ListCollectionsRequest(_message.Message):
    __slots__ = ("dataset_id", "with_availability", "with_count")
    DATASET_ID_FIELD_NUMBER: _ClassVar[int]
    WITH_AVAILABILITY_FIELD_NUMBER: _ClassVar[int]
    WITH_COUNT_FIELD_NUMBER: _ClassVar[int]
    dataset_id: _id_pb2.ID
    with_availability: bool
    with_count: bool
    def __init__(self, dataset_id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ..., with_availability: bool = ..., with_count: bool = ...) -> None: ...
