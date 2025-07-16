from tilebox.datasets.datasets.v1 import core_pb2 as _core_pb2
from tilebox.datasets.tilebox.v1 import id_pb2 as _id_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class IngestDatapointsRequest(_message.Message):
    __slots__ = ("collection_id", "datapoints", "allow_existing")
    COLLECTION_ID_FIELD_NUMBER: _ClassVar[int]
    DATAPOINTS_FIELD_NUMBER: _ClassVar[int]
    ALLOW_EXISTING_FIELD_NUMBER: _ClassVar[int]
    collection_id: _id_pb2.ID
    datapoints: _core_pb2.Datapoints
    allow_existing: bool
    def __init__(self, collection_id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ..., datapoints: _Optional[_Union[_core_pb2.Datapoints, _Mapping]] = ..., allow_existing: bool = ...) -> None: ...

class IngestRequest(_message.Message):
    __slots__ = ("collection_id", "values", "allow_existing")
    COLLECTION_ID_FIELD_NUMBER: _ClassVar[int]
    VALUES_FIELD_NUMBER: _ClassVar[int]
    ALLOW_EXISTING_FIELD_NUMBER: _ClassVar[int]
    collection_id: _id_pb2.ID
    values: _containers.RepeatedScalarFieldContainer[bytes]
    allow_existing: bool
    def __init__(self, collection_id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ..., values: _Optional[_Iterable[bytes]] = ..., allow_existing: bool = ...) -> None: ...

class IngestResponse(_message.Message):
    __slots__ = ("num_created", "num_existing", "datapoint_ids")
    NUM_CREATED_FIELD_NUMBER: _ClassVar[int]
    NUM_EXISTING_FIELD_NUMBER: _ClassVar[int]
    DATAPOINT_IDS_FIELD_NUMBER: _ClassVar[int]
    num_created: int
    num_existing: int
    datapoint_ids: _containers.RepeatedCompositeFieldContainer[_id_pb2.ID]
    def __init__(self, num_created: _Optional[int] = ..., num_existing: _Optional[int] = ..., datapoint_ids: _Optional[_Iterable[_Union[_id_pb2.ID, _Mapping]]] = ...) -> None: ...

class DeleteRequest(_message.Message):
    __slots__ = ("collection_id", "datapoint_ids")
    COLLECTION_ID_FIELD_NUMBER: _ClassVar[int]
    DATAPOINT_IDS_FIELD_NUMBER: _ClassVar[int]
    collection_id: _id_pb2.ID
    datapoint_ids: _containers.RepeatedCompositeFieldContainer[_id_pb2.ID]
    def __init__(self, collection_id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ..., datapoint_ids: _Optional[_Iterable[_Union[_id_pb2.ID, _Mapping]]] = ...) -> None: ...

class DeleteResponse(_message.Message):
    __slots__ = ("num_deleted",)
    NUM_DELETED_FIELD_NUMBER: _ClassVar[int]
    num_deleted: int
    def __init__(self, num_deleted: _Optional[int] = ...) -> None: ...
