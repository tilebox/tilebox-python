from tilebox.datasets.datasets.v1 import core_pb2 as _core_pb2
from tilebox.datasets.datasets.v1 import dataset_type_pb2 as _dataset_type_pb2
from tilebox.datasets.tilebox.v1 import id_pb2 as _id_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class CreateDatasetRequest(_message.Message):
    __slots__ = ("name", "type", "summary", "code_name")
    NAME_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    SUMMARY_FIELD_NUMBER: _ClassVar[int]
    CODE_NAME_FIELD_NUMBER: _ClassVar[int]
    name: str
    type: _dataset_type_pb2.DatasetType
    summary: str
    code_name: str
    def __init__(self, name: _Optional[str] = ..., type: _Optional[_Union[_dataset_type_pb2.DatasetType, _Mapping]] = ..., summary: _Optional[str] = ..., code_name: _Optional[str] = ...) -> None: ...

class GetDatasetRequest(_message.Message):
    __slots__ = ("slug", "id")
    SLUG_FIELD_NUMBER: _ClassVar[int]
    ID_FIELD_NUMBER: _ClassVar[int]
    slug: str
    id: _id_pb2.ID
    def __init__(self, slug: _Optional[str] = ..., id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ...) -> None: ...

class UpdateDatasetRequest(_message.Message):
    __slots__ = ("id", "name", "type", "summary")
    ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    SUMMARY_FIELD_NUMBER: _ClassVar[int]
    id: _id_pb2.ID
    name: str
    type: _dataset_type_pb2.DatasetType
    summary: str
    def __init__(self, id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ..., name: _Optional[str] = ..., type: _Optional[_Union[_dataset_type_pb2.DatasetType, _Mapping]] = ..., summary: _Optional[str] = ...) -> None: ...

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
    id: _id_pb2.ID
    description: str
    def __init__(self, id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ..., description: _Optional[str] = ...) -> None: ...

class DeleteDatasetRequest(_message.Message):
    __slots__ = ("id",)
    ID_FIELD_NUMBER: _ClassVar[int]
    id: _id_pb2.ID
    def __init__(self, id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ...) -> None: ...

class DeleteDatasetResponse(_message.Message):
    __slots__ = ("trashed",)
    TRASHED_FIELD_NUMBER: _ClassVar[int]
    trashed: bool
    def __init__(self, trashed: bool = ...) -> None: ...

class ListDatasetsRequest(_message.Message):
    __slots__ = ("client_info",)
    CLIENT_INFO_FIELD_NUMBER: _ClassVar[int]
    client_info: ClientInfo
    def __init__(self, client_info: _Optional[_Union[ClientInfo, _Mapping]] = ...) -> None: ...

class ListDatasetsResponse(_message.Message):
    __slots__ = ("datasets", "groups", "server_message", "owned_datasets", "maximum_owned_datasets")
    DATASETS_FIELD_NUMBER: _ClassVar[int]
    GROUPS_FIELD_NUMBER: _ClassVar[int]
    SERVER_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    OWNED_DATASETS_FIELD_NUMBER: _ClassVar[int]
    MAXIMUM_OWNED_DATASETS_FIELD_NUMBER: _ClassVar[int]
    datasets: _containers.RepeatedCompositeFieldContainer[_core_pb2.Dataset]
    groups: _containers.RepeatedCompositeFieldContainer[_core_pb2.DatasetGroup]
    server_message: str
    owned_datasets: int
    maximum_owned_datasets: int
    def __init__(self, datasets: _Optional[_Iterable[_Union[_core_pb2.Dataset, _Mapping]]] = ..., groups: _Optional[_Iterable[_Union[_core_pb2.DatasetGroup, _Mapping]]] = ..., server_message: _Optional[str] = ..., owned_datasets: _Optional[int] = ..., maximum_owned_datasets: _Optional[int] = ...) -> None: ...
