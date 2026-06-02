from tilebox.datasets.buf.validate import validate_pb2 as _validate_pb2
from google.protobuf import empty_pb2 as _empty_pb2
from tilebox.datasets.tilebox.v1 import id_pb2 as _id_pb2
from tilebox.workflows.workflows.v1 import automation_pb2 as _automation_pb2
from tilebox.workflows.workflows.v1 import core_pb2 as _core_pb2
from tilebox.workflows.workflows.v1 import task_pb2 as _task_pb2
from tilebox.workflows.workflows.v1 import workflows_pb2 as _workflows_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class InitializeRunnerRequest(_message.Message):
    __slots__ = ("runner_id", "trace_parent", "cluster", "workflow", "locations")
    RUNNER_ID_FIELD_NUMBER: _ClassVar[int]
    TRACE_PARENT_FIELD_NUMBER: _ClassVar[int]
    CLUSTER_FIELD_NUMBER: _ClassVar[int]
    WORKFLOW_FIELD_NUMBER: _ClassVar[int]
    LOCATIONS_FIELD_NUMBER: _ClassVar[int]
    runner_id: _id_pb2.ID
    trace_parent: str
    cluster: _workflows_pb2.Cluster
    workflow: _workflows_pb2.Workflow
    locations: _containers.RepeatedCompositeFieldContainer[_automation_pb2.StorageLocation]
    def __init__(self, runner_id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ..., trace_parent: _Optional[str] = ..., cluster: _Optional[_Union[_workflows_pb2.Cluster, _Mapping]] = ..., workflow: _Optional[_Union[_workflows_pb2.Workflow, _Mapping]] = ..., locations: _Optional[_Iterable[_Union[_automation_pb2.StorageLocation, _Mapping]]] = ...) -> None: ...

class InitializeRunnerResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ExecuteTaskResponse(_message.Message):
    __slots__ = ("computed_task", "failed_task")
    COMPUTED_TASK_FIELD_NUMBER: _ClassVar[int]
    FAILED_TASK_FIELD_NUMBER: _ClassVar[int]
    computed_task: _task_pb2.ComputedTask
    failed_task: _task_pb2.TaskFailedRequest
    def __init__(self, computed_task: _Optional[_Union[_task_pb2.ComputedTask, _Mapping]] = ..., failed_task: _Optional[_Union[_task_pb2.TaskFailedRequest, _Mapping]] = ...) -> None: ...
