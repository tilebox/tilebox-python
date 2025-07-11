from tilebox.workflows.workflows.v1 import core_pb2 as _core_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class CreateClusterRequest(_message.Message):
    __slots__ = ("name",)
    NAME_FIELD_NUMBER: _ClassVar[int]
    name: str
    def __init__(self, name: _Optional[str] = ...) -> None: ...

class GetClusterRequest(_message.Message):
    __slots__ = ("cluster_slug",)
    CLUSTER_SLUG_FIELD_NUMBER: _ClassVar[int]
    cluster_slug: str
    def __init__(self, cluster_slug: _Optional[str] = ...) -> None: ...

class DeleteClusterRequest(_message.Message):
    __slots__ = ("cluster_slug",)
    CLUSTER_SLUG_FIELD_NUMBER: _ClassVar[int]
    cluster_slug: str
    def __init__(self, cluster_slug: _Optional[str] = ...) -> None: ...

class DeleteClusterResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ListClustersRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ListClustersResponse(_message.Message):
    __slots__ = ("clusters",)
    CLUSTERS_FIELD_NUMBER: _ClassVar[int]
    clusters: _containers.RepeatedCompositeFieldContainer[_core_pb2.Cluster]
    def __init__(self, clusters: _Optional[_Iterable[_Union[_core_pb2.Cluster, _Mapping]]] = ...) -> None: ...
