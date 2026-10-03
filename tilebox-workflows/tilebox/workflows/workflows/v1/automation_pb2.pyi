from google.api import field_behavior_pb2 as _field_behavior_pb2
from google.protobuf import empty_pb2 as _empty_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from tilebox.datasets.tilebox.v1 import id_pb2 as _id_pb2
from tilebox.workflows.workflows.v1 import core_pb2 as _core_pb2
from tilebox.workflows.workflows.v1 import storage_location_pb2 as _storage_location_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class AutomationPrototype(_message.Message):
    __slots__ = ("id", "name", "prototype", "storage_event_triggers", "cron_triggers", "disabled")
    ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    PROTOTYPE_FIELD_NUMBER: _ClassVar[int]
    STORAGE_EVENT_TRIGGERS_FIELD_NUMBER: _ClassVar[int]
    CRON_TRIGGERS_FIELD_NUMBER: _ClassVar[int]
    DISABLED_FIELD_NUMBER: _ClassVar[int]
    id: _id_pb2.ID
    name: str
    prototype: _core_pb2.SingleTaskSubmission
    storage_event_triggers: _containers.RepeatedCompositeFieldContainer[StorageEventTrigger]
    cron_triggers: _containers.RepeatedCompositeFieldContainer[CronTrigger]
    disabled: bool
    def __init__(self, id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ..., name: _Optional[str] = ..., prototype: _Optional[_Union[_core_pb2.SingleTaskSubmission, _Mapping]] = ..., storage_event_triggers: _Optional[_Iterable[_Union[StorageEventTrigger, _Mapping]]] = ..., cron_triggers: _Optional[_Iterable[_Union[CronTrigger, _Mapping]]] = ..., disabled: bool = ...) -> None: ...

class Automations(_message.Message):
    __slots__ = ("automations",)
    AUTOMATIONS_FIELD_NUMBER: _ClassVar[int]
    automations: _containers.RepeatedCompositeFieldContainer[AutomationPrototype]
    def __init__(self, automations: _Optional[_Iterable[_Union[AutomationPrototype, _Mapping]]] = ...) -> None: ...

class StorageEventTrigger(_message.Message):
    __slots__ = ("id", "storage_location", "glob_pattern")
    ID_FIELD_NUMBER: _ClassVar[int]
    STORAGE_LOCATION_FIELD_NUMBER: _ClassVar[int]
    GLOB_PATTERN_FIELD_NUMBER: _ClassVar[int]
    id: _id_pb2.ID
    storage_location: _storage_location_pb2.StorageLocation
    glob_pattern: str
    def __init__(self, id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ..., storage_location: _Optional[_Union[_storage_location_pb2.StorageLocation, _Mapping]] = ..., glob_pattern: _Optional[str] = ...) -> None: ...

class CronTrigger(_message.Message):
    __slots__ = ("id", "schedule", "next_scheduled_at")
    ID_FIELD_NUMBER: _ClassVar[int]
    SCHEDULE_FIELD_NUMBER: _ClassVar[int]
    NEXT_SCHEDULED_AT_FIELD_NUMBER: _ClassVar[int]
    id: _id_pb2.ID
    schedule: str
    next_scheduled_at: _timestamp_pb2.Timestamp
    def __init__(self, id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ..., schedule: _Optional[str] = ..., next_scheduled_at: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class Automation(_message.Message):
    __slots__ = ("trigger_event", "args")
    TRIGGER_EVENT_FIELD_NUMBER: _ClassVar[int]
    ARGS_FIELD_NUMBER: _ClassVar[int]
    trigger_event: bytes
    args: bytes
    def __init__(self, trigger_event: _Optional[bytes] = ..., args: _Optional[bytes] = ...) -> None: ...

class TriggeredCronEvent(_message.Message):
    __slots__ = ("trigger_time",)
    TRIGGER_TIME_FIELD_NUMBER: _ClassVar[int]
    trigger_time: _timestamp_pb2.Timestamp
    def __init__(self, trigger_time: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class DeleteAutomationRequest(_message.Message):
    __slots__ = ("automation_id", "cancel_jobs")
    AUTOMATION_ID_FIELD_NUMBER: _ClassVar[int]
    CANCEL_JOBS_FIELD_NUMBER: _ClassVar[int]
    automation_id: _id_pb2.ID
    cancel_jobs: bool
    def __init__(self, automation_id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ..., cancel_jobs: bool = ...) -> None: ...
