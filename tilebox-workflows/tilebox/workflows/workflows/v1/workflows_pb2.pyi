from tilebox.datasets.buf.validate import validate_pb2 as _validate_pb2
from google.protobuf import empty_pb2 as _empty_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from tilebox.datasets.tilebox.v1 import id_pb2 as _id_pb2
from tilebox.workflows.workflows.v1 import core_pb2 as _core_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Cluster(_message.Message):
    __slots__ = ("slug", "display_name", "description", "deletable", "deployed_releases")
    SLUG_FIELD_NUMBER: _ClassVar[int]
    DISPLAY_NAME_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    DELETABLE_FIELD_NUMBER: _ClassVar[int]
    DEPLOYED_RELEASES_FIELD_NUMBER: _ClassVar[int]
    slug: str
    display_name: str
    description: str
    deletable: bool
    deployed_releases: _containers.RepeatedCompositeFieldContainer[Workflow]
    def __init__(self, slug: _Optional[str] = ..., display_name: _Optional[str] = ..., description: _Optional[str] = ..., deletable: bool = ..., deployed_releases: _Optional[_Iterable[_Union[Workflow, _Mapping]]] = ...) -> None: ...

class CreateClusterRequest(_message.Message):
    __slots__ = ("name", "description", "slug")
    NAME_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    SLUG_FIELD_NUMBER: _ClassVar[int]
    name: str
    description: str
    slug: str
    def __init__(self, name: _Optional[str] = ..., description: _Optional[str] = ..., slug: _Optional[str] = ...) -> None: ...

class GetClusterRequest(_message.Message):
    __slots__ = ("cluster_slug",)
    CLUSTER_SLUG_FIELD_NUMBER: _ClassVar[int]
    cluster_slug: str
    def __init__(self, cluster_slug: _Optional[str] = ...) -> None: ...

class UpdateClusterRequest(_message.Message):
    __slots__ = ("cluster_slug", "name", "description")
    CLUSTER_SLUG_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    cluster_slug: str
    name: str
    description: str
    def __init__(self, cluster_slug: _Optional[str] = ..., name: _Optional[str] = ..., description: _Optional[str] = ...) -> None: ...

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
    clusters: _containers.RepeatedCompositeFieldContainer[Cluster]
    def __init__(self, clusters: _Optional[_Iterable[_Union[Cluster, _Mapping]]] = ...) -> None: ...

class GetWorkflowRequest(_message.Message):
    __slots__ = ("workflow_slug",)
    WORKFLOW_SLUG_FIELD_NUMBER: _ClassVar[int]
    workflow_slug: str
    def __init__(self, workflow_slug: _Optional[str] = ...) -> None: ...

class UpdateWorkflowRequest(_message.Message):
    __slots__ = ("workflow_slug", "name", "description")
    WORKFLOW_SLUG_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    workflow_slug: str
    name: str
    description: str
    def __init__(self, workflow_slug: _Optional[str] = ..., name: _Optional[str] = ..., description: _Optional[str] = ...) -> None: ...

class DeleteWorkflowRequest(_message.Message):
    __slots__ = ("workflow_slug",)
    WORKFLOW_SLUG_FIELD_NUMBER: _ClassVar[int]
    workflow_slug: str
    def __init__(self, workflow_slug: _Optional[str] = ...) -> None: ...

class DeleteWorkflowResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class PublishWorkflowReleaseRequest(_message.Message):
    __slots__ = ("workflow_slug", "artifact_id", "content")
    WORKFLOW_SLUG_FIELD_NUMBER: _ClassVar[int]
    ARTIFACT_ID_FIELD_NUMBER: _ClassVar[int]
    CONTENT_FIELD_NUMBER: _ClassVar[int]
    workflow_slug: str
    artifact_id: _id_pb2.ID
    content: ReleaseContent
    def __init__(self, workflow_slug: _Optional[str] = ..., artifact_id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ..., content: _Optional[_Union[ReleaseContent, _Mapping]] = ...) -> None: ...

class UnpublishWorkflowReleaseRequest(_message.Message):
    __slots__ = ("workflow_slug", "release_id")
    WORKFLOW_SLUG_FIELD_NUMBER: _ClassVar[int]
    RELEASE_ID_FIELD_NUMBER: _ClassVar[int]
    workflow_slug: str
    release_id: _id_pb2.ID
    def __init__(self, workflow_slug: _Optional[str] = ..., release_id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ...) -> None: ...

class UnpublishWorkflowReleaseResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ListWorkflowsRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ListWorkflowsResponse(_message.Message):
    __slots__ = ("workflows",)
    WORKFLOWS_FIELD_NUMBER: _ClassVar[int]
    workflows: _containers.RepeatedCompositeFieldContainer[Workflow]
    def __init__(self, workflows: _Optional[_Iterable[_Union[Workflow, _Mapping]]] = ...) -> None: ...

class CreateWorkflowRequest(_message.Message):
    __slots__ = ("name", "description")
    NAME_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    name: str
    description: str
    def __init__(self, name: _Optional[str] = ..., description: _Optional[str] = ...) -> None: ...

class Workflow(_message.Message):
    __slots__ = ("slug", "name", "description", "releases")
    SLUG_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    RELEASES_FIELD_NUMBER: _ClassVar[int]
    slug: str
    name: str
    description: str
    releases: _containers.RepeatedCompositeFieldContainer[WorkflowRelease]
    def __init__(self, slug: _Optional[str] = ..., name: _Optional[str] = ..., description: _Optional[str] = ..., releases: _Optional[_Iterable[_Union[WorkflowRelease, _Mapping]]] = ...) -> None: ...

class WorkflowRelease(_message.Message):
    __slots__ = ("id", "artifact", "content", "created_at", "clusters")
    ID_FIELD_NUMBER: _ClassVar[int]
    ARTIFACT_FIELD_NUMBER: _ClassVar[int]
    CONTENT_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    CLUSTERS_FIELD_NUMBER: _ClassVar[int]
    id: _id_pb2.ID
    artifact: Artifact
    content: ReleaseContent
    created_at: _timestamp_pb2.Timestamp
    clusters: _containers.RepeatedCompositeFieldContainer[Cluster]
    def __init__(self, id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ..., artifact: _Optional[_Union[Artifact, _Mapping]] = ..., content: _Optional[_Union[ReleaseContent, _Mapping]] = ..., created_at: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., clusters: _Optional[_Iterable[_Union[Cluster, _Mapping]]] = ...) -> None: ...

class Artifact(_message.Message):
    __slots__ = ("id", "digest")
    ID_FIELD_NUMBER: _ClassVar[int]
    DIGEST_FIELD_NUMBER: _ClassVar[int]
    id: _id_pb2.ID
    digest: str
    def __init__(self, id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ..., digest: _Optional[str] = ...) -> None: ...

class ReleaseContent(_message.Message):
    __slots__ = ("fingerprint", "tasks", "files", "runner_object_path", "command_override")
    FINGERPRINT_FIELD_NUMBER: _ClassVar[int]
    TASKS_FIELD_NUMBER: _ClassVar[int]
    FILES_FIELD_NUMBER: _ClassVar[int]
    RUNNER_OBJECT_PATH_FIELD_NUMBER: _ClassVar[int]
    COMMAND_OVERRIDE_FIELD_NUMBER: _ClassVar[int]
    fingerprint: str
    tasks: _containers.RepeatedCompositeFieldContainer[_core_pb2.TaskIdentifier]
    files: _containers.RepeatedCompositeFieldContainer[Path]
    runner_object_path: str
    command_override: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, fingerprint: _Optional[str] = ..., tasks: _Optional[_Iterable[_Union[_core_pb2.TaskIdentifier, _Mapping]]] = ..., files: _Optional[_Iterable[_Union[Path, _Mapping]]] = ..., runner_object_path: _Optional[str] = ..., command_override: _Optional[_Iterable[str]] = ...) -> None: ...

class Path(_message.Message):
    __slots__ = ("path", "directory", "children")
    PATH_FIELD_NUMBER: _ClassVar[int]
    DIRECTORY_FIELD_NUMBER: _ClassVar[int]
    CHILDREN_FIELD_NUMBER: _ClassVar[int]
    path: str
    directory: bool
    children: _containers.RepeatedCompositeFieldContainer[Path]
    def __init__(self, path: _Optional[str] = ..., directory: bool = ..., children: _Optional[_Iterable[_Union[Path, _Mapping]]] = ...) -> None: ...

class DeployWorkflowReleaseRequest(_message.Message):
    __slots__ = ("workflow_slug", "release_id", "cluster_slugs")
    WORKFLOW_SLUG_FIELD_NUMBER: _ClassVar[int]
    RELEASE_ID_FIELD_NUMBER: _ClassVar[int]
    CLUSTER_SLUGS_FIELD_NUMBER: _ClassVar[int]
    workflow_slug: str
    release_id: _id_pb2.ID
    cluster_slugs: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, workflow_slug: _Optional[str] = ..., release_id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ..., cluster_slugs: _Optional[_Iterable[str]] = ...) -> None: ...

class DeployWorkflowReleaseResponse(_message.Message):
    __slots__ = ("release", "clusters")
    RELEASE_FIELD_NUMBER: _ClassVar[int]
    CLUSTERS_FIELD_NUMBER: _ClassVar[int]
    release: WorkflowRelease
    clusters: _containers.RepeatedCompositeFieldContainer[Cluster]
    def __init__(self, release: _Optional[_Union[WorkflowRelease, _Mapping]] = ..., clusters: _Optional[_Iterable[_Union[Cluster, _Mapping]]] = ...) -> None: ...

class UndeployWorkflowReleaseRequest(_message.Message):
    __slots__ = ("workflow_slug", "release_id", "cluster_slugs")
    WORKFLOW_SLUG_FIELD_NUMBER: _ClassVar[int]
    RELEASE_ID_FIELD_NUMBER: _ClassVar[int]
    CLUSTER_SLUGS_FIELD_NUMBER: _ClassVar[int]
    workflow_slug: str
    release_id: _id_pb2.ID
    cluster_slugs: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, workflow_slug: _Optional[str] = ..., release_id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ..., cluster_slugs: _Optional[_Iterable[str]] = ...) -> None: ...

class UndeployWorkflowReleaseResponse(_message.Message):
    __slots__ = ("release", "clusters")
    RELEASE_FIELD_NUMBER: _ClassVar[int]
    CLUSTERS_FIELD_NUMBER: _ClassVar[int]
    release: WorkflowRelease
    clusters: _containers.RepeatedCompositeFieldContainer[Cluster]
    def __init__(self, release: _Optional[_Union[WorkflowRelease, _Mapping]] = ..., clusters: _Optional[_Iterable[_Union[Cluster, _Mapping]]] = ...) -> None: ...
