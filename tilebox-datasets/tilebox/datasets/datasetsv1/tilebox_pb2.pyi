from tilebox.datasets.datasetsv1 import core_pb2 as _core_pb2
from tilebox.datasets.datasetsv1 import dataset_type_pb2 as _dataset_type_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class CreateDatasetRequest(_message.Message):
    __slots__ = ("name", "type", "summary")
    NAME_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    SUMMARY_FIELD_NUMBER: _ClassVar[int]
    name: str
    type: _dataset_type_pb2.DatasetType
    summary: str
    def __init__(self, name: _Optional[str] = ..., type: _Optional[_Union[_dataset_type_pb2.DatasetType, _Mapping]] = ..., summary: _Optional[str] = ...) -> None: ...

class GetDatasetRequest(_message.Message):
    __slots__ = ("slug", "id")
    SLUG_FIELD_NUMBER: _ClassVar[int]
    ID_FIELD_NUMBER: _ClassVar[int]
    slug: str
    id: str
    def __init__(self, slug: _Optional[str] = ..., id: _Optional[str] = ...) -> None: ...

class UpdateDatasetRequest(_message.Message):
    __slots__ = ("id", "name", "type", "summary")
    ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    SUMMARY_FIELD_NUMBER: _ClassVar[int]
    id: _core_pb2.ID
    name: str
    type: _dataset_type_pb2.DatasetType
    summary: str
    def __init__(self, id: _Optional[_Union[_core_pb2.ID, _Mapping]] = ..., name: _Optional[str] = ..., type: _Optional[_Union[_dataset_type_pb2.DatasetType, _Mapping]] = ..., summary: _Optional[str] = ...) -> None: ...

class ClientInfo(_message.Message):
    __slots__ = ("name", "environment", "packages")
    NAME_FIELD_NUMBER: _ClassVar[int]
    ENVIRONMENT_FIELD_NUMBER: _ClassVar[int]
    PACKAGES_FIELD_NUMBER: _ClassVar[int]
    name: str
    environment: str
    packages: _containers.RepeatedCompositeFieldContainer[Package]
    def __init__(self, name: _Optional[str] = ..., environment: _Optional[str] = ..., packages: _Optional[_Iterable[_Union[Package, _Mapping]]] = ...) -> None: ...

class Package(_message.Message):
    __slots__ = ("name", "version")
    NAME_FIELD_NUMBER: _ClassVar[int]
    VERSION_FIELD_NUMBER: _ClassVar[int]
    name: str
    version: str
    def __init__(self, name: _Optional[str] = ..., version: _Optional[str] = ...) -> None: ...

class UpdateDatasetDescriptionRequest(_message.Message):
    __slots__ = ("id", "description")
    ID_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    id: _core_pb2.ID
    description: str
    def __init__(self, id: _Optional[_Union[_core_pb2.ID, _Mapping]] = ..., description: _Optional[str] = ...) -> None: ...

class ListDatasetsRequest(_message.Message):
    __slots__ = ("client_info",)
    CLIENT_INFO_FIELD_NUMBER: _ClassVar[int]
    client_info: ClientInfo
    def __init__(self, client_info: _Optional[_Union[ClientInfo, _Mapping]] = ...) -> None: ...

class ListDatasetsResponse(_message.Message):
    __slots__ = ("datasets", "groups", "server_message")
    DATASETS_FIELD_NUMBER: _ClassVar[int]
    GROUPS_FIELD_NUMBER: _ClassVar[int]
    SERVER_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    datasets: _containers.RepeatedCompositeFieldContainer[_core_pb2.Dataset]
    groups: _containers.RepeatedCompositeFieldContainer[_core_pb2.DatasetGroup]
    server_message: str
    def __init__(self, datasets: _Optional[_Iterable[_Union[_core_pb2.Dataset, _Mapping]]] = ..., groups: _Optional[_Iterable[_Union[_core_pb2.DatasetGroup, _Mapping]]] = ..., server_message: _Optional[str] = ...) -> None: ...

class Datapoints(_message.Message):
    __slots__ = ("meta", "data", "next_page")
    META_FIELD_NUMBER: _ClassVar[int]
    DATA_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_FIELD_NUMBER: _ClassVar[int]
    meta: _containers.RepeatedCompositeFieldContainer[_core_pb2.DatapointMetadata]
    data: _core_pb2.RepeatedAny
    next_page: _core_pb2.Pagination
    def __init__(self, meta: _Optional[_Iterable[_Union[_core_pb2.DatapointMetadata, _Mapping]]] = ..., data: _Optional[_Union[_core_pb2.RepeatedAny, _Mapping]] = ..., next_page: _Optional[_Union[_core_pb2.Pagination, _Mapping]] = ...) -> None: ...

class Datapoint(_message.Message):
    __slots__ = ("meta", "data")
    META_FIELD_NUMBER: _ClassVar[int]
    DATA_FIELD_NUMBER: _ClassVar[int]
    meta: _core_pb2.DatapointMetadata
    data: _core_pb2.Any
    def __init__(self, meta: _Optional[_Union[_core_pb2.DatapointMetadata, _Mapping]] = ..., data: _Optional[_Union[_core_pb2.Any, _Mapping]] = ...) -> None: ...

class IngestDatapointsRequest(_message.Message):
    __slots__ = ("collection_id", "datapoints", "allow_existing")
    COLLECTION_ID_FIELD_NUMBER: _ClassVar[int]
    DATAPOINTS_FIELD_NUMBER: _ClassVar[int]
    ALLOW_EXISTING_FIELD_NUMBER: _ClassVar[int]
    collection_id: _core_pb2.ID
    datapoints: Datapoints
    allow_existing: bool
    def __init__(self, collection_id: _Optional[_Union[_core_pb2.ID, _Mapping]] = ..., datapoints: _Optional[_Union[Datapoints, _Mapping]] = ..., allow_existing: bool = ...) -> None: ...

class IngestDatapointsResponse(_message.Message):
    __slots__ = ("num_created", "num_existing", "datapoint_ids")
    NUM_CREATED_FIELD_NUMBER: _ClassVar[int]
    NUM_EXISTING_FIELD_NUMBER: _ClassVar[int]
    DATAPOINT_IDS_FIELD_NUMBER: _ClassVar[int]
    num_created: int
    num_existing: int
    datapoint_ids: _containers.RepeatedCompositeFieldContainer[_core_pb2.ID]
    def __init__(self, num_created: _Optional[int] = ..., num_existing: _Optional[int] = ..., datapoint_ids: _Optional[_Iterable[_Union[_core_pb2.ID, _Mapping]]] = ...) -> None: ...

class DeleteDatapointsRequest(_message.Message):
    __slots__ = ("collection_id", "datapoint_ids")
    COLLECTION_ID_FIELD_NUMBER: _ClassVar[int]
    DATAPOINT_IDS_FIELD_NUMBER: _ClassVar[int]
    collection_id: _core_pb2.ID
    datapoint_ids: _containers.RepeatedCompositeFieldContainer[_core_pb2.ID]
    def __init__(self, collection_id: _Optional[_Union[_core_pb2.ID, _Mapping]] = ..., datapoint_ids: _Optional[_Iterable[_Union[_core_pb2.ID, _Mapping]]] = ...) -> None: ...

class DeleteDatapointsResponse(_message.Message):
    __slots__ = ("num_deleted",)
    NUM_DELETED_FIELD_NUMBER: _ClassVar[int]
    num_deleted: int
    def __init__(self, num_deleted: _Optional[int] = ...) -> None: ...
