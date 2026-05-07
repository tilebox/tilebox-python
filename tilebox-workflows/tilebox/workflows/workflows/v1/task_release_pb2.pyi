from tilebox.datasets.buf.validate import validate_pb2 as _validate_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from tilebox.datasets.tilebox.v1 import id_pb2 as _id_pb2
from tilebox.workflows.workflows.v1 import core_pb2 as _core_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class PublishReleaseRequest(_message.Message):
    __slots__ = ("tasks", "artifact_uri", "artifact_digest", "runtime_kind", "environment_digest", "metadata_json")
    TASKS_FIELD_NUMBER: _ClassVar[int]
    ARTIFACT_URI_FIELD_NUMBER: _ClassVar[int]
    ARTIFACT_DIGEST_FIELD_NUMBER: _ClassVar[int]
    RUNTIME_KIND_FIELD_NUMBER: _ClassVar[int]
    ENVIRONMENT_DIGEST_FIELD_NUMBER: _ClassVar[int]
    METADATA_JSON_FIELD_NUMBER: _ClassVar[int]
    tasks: _containers.RepeatedCompositeFieldContainer[_core_pb2.TaskIdentifier]
    artifact_uri: str
    artifact_digest: str
    runtime_kind: str
    environment_digest: str
    metadata_json: bytes
    def __init__(self, tasks: _Optional[_Iterable[_Union[_core_pb2.TaskIdentifier, _Mapping]]] = ..., artifact_uri: _Optional[str] = ..., artifact_digest: _Optional[str] = ..., runtime_kind: _Optional[str] = ..., environment_digest: _Optional[str] = ..., metadata_json: _Optional[bytes] = ...) -> None: ...

class PublishReleaseResponse(_message.Message):
    __slots__ = ("release_id", "created", "changes")
    RELEASE_ID_FIELD_NUMBER: _ClassVar[int]
    CREATED_FIELD_NUMBER: _ClassVar[int]
    CHANGES_FIELD_NUMBER: _ClassVar[int]
    release_id: _id_pb2.ID
    created: bool
    changes: PublishReleaseChanges
    def __init__(self, release_id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ..., created: bool = ..., changes: _Optional[_Union[PublishReleaseChanges, _Mapping]] = ...) -> None: ...

class PublishReleaseChanges(_message.Message):
    __slots__ = ("tasks", "artifact", "environment")
    TASKS_FIELD_NUMBER: _ClassVar[int]
    ARTIFACT_FIELD_NUMBER: _ClassVar[int]
    ENVIRONMENT_FIELD_NUMBER: _ClassVar[int]
    tasks: bool
    artifact: bool
    environment: bool
    def __init__(self, tasks: bool = ..., artifact: bool = ..., environment: bool = ...) -> None: ...

class DeployReleaseRequest(_message.Message):
    __slots__ = ("cluster_slug", "release_id")
    CLUSTER_SLUG_FIELD_NUMBER: _ClassVar[int]
    RELEASE_ID_FIELD_NUMBER: _ClassVar[int]
    cluster_slug: str
    release_id: _id_pb2.ID
    def __init__(self, cluster_slug: _Optional[str] = ..., release_id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ...) -> None: ...

class DeployReleaseResponse(_message.Message):
    __slots__ = ("cluster_slug", "release_id", "manifest_revision", "changed")
    CLUSTER_SLUG_FIELD_NUMBER: _ClassVar[int]
    RELEASE_ID_FIELD_NUMBER: _ClassVar[int]
    MANIFEST_REVISION_FIELD_NUMBER: _ClassVar[int]
    CHANGED_FIELD_NUMBER: _ClassVar[int]
    cluster_slug: str
    release_id: _id_pb2.ID
    manifest_revision: int
    changed: bool
    def __init__(self, cluster_slug: _Optional[str] = ..., release_id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ..., manifest_revision: _Optional[int] = ..., changed: bool = ...) -> None: ...

class GetClusterDeploymentManifestRequest(_message.Message):
    __slots__ = ("cluster_slug", "since_revision")
    CLUSTER_SLUG_FIELD_NUMBER: _ClassVar[int]
    SINCE_REVISION_FIELD_NUMBER: _ClassVar[int]
    cluster_slug: str
    since_revision: int
    def __init__(self, cluster_slug: _Optional[str] = ..., since_revision: _Optional[int] = ...) -> None: ...

class DeployedRelease(_message.Message):
    __slots__ = ("release_id", "artifact_uri", "artifact_digest", "runtime_kind", "environment_digest", "metadata_json", "change_revision", "tasks", "deployed_at")
    RELEASE_ID_FIELD_NUMBER: _ClassVar[int]
    ARTIFACT_URI_FIELD_NUMBER: _ClassVar[int]
    ARTIFACT_DIGEST_FIELD_NUMBER: _ClassVar[int]
    RUNTIME_KIND_FIELD_NUMBER: _ClassVar[int]
    ENVIRONMENT_DIGEST_FIELD_NUMBER: _ClassVar[int]
    METADATA_JSON_FIELD_NUMBER: _ClassVar[int]
    CHANGE_REVISION_FIELD_NUMBER: _ClassVar[int]
    TASKS_FIELD_NUMBER: _ClassVar[int]
    DEPLOYED_AT_FIELD_NUMBER: _ClassVar[int]
    release_id: _id_pb2.ID
    artifact_uri: str
    artifact_digest: str
    runtime_kind: str
    environment_digest: str
    metadata_json: bytes
    change_revision: int
    tasks: _containers.RepeatedCompositeFieldContainer[_core_pb2.TaskIdentifier]
    deployed_at: _timestamp_pb2.Timestamp
    def __init__(self, release_id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ..., artifact_uri: _Optional[str] = ..., artifact_digest: _Optional[str] = ..., runtime_kind: _Optional[str] = ..., environment_digest: _Optional[str] = ..., metadata_json: _Optional[bytes] = ..., change_revision: _Optional[int] = ..., tasks: _Optional[_Iterable[_Union[_core_pb2.TaskIdentifier, _Mapping]]] = ..., deployed_at: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class GetClusterDeploymentManifestResponse(_message.Message):
    __slots__ = ("cluster_slug", "manifest_revision", "release")
    CLUSTER_SLUG_FIELD_NUMBER: _ClassVar[int]
    MANIFEST_REVISION_FIELD_NUMBER: _ClassVar[int]
    RELEASE_FIELD_NUMBER: _ClassVar[int]
    cluster_slug: str
    manifest_revision: int
    release: DeployedRelease
    def __init__(self, cluster_slug: _Optional[str] = ..., manifest_revision: _Optional[int] = ..., release: _Optional[_Union[DeployedRelease, _Mapping]] = ...) -> None: ...
