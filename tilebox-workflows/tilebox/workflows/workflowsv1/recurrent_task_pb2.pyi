from tilebox.workflows.workflowsv1 import core_pb2 as _core_pb2
from google.protobuf import empty_pb2 as _empty_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class StorageType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    STORAGE_TYPE_UNSPECIFIED: _ClassVar[StorageType]
    STORAGE_TYPE_GCS: _ClassVar[StorageType]
    STORAGE_TYPE_S3: _ClassVar[StorageType]
    STORAGE_TYPE_FS: _ClassVar[StorageType]

class StorageEventType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    STORAGE_EVENT_TYPE_UNSPECIFIED: _ClassVar[StorageEventType]
    STORAGE_EVENT_TYPE_CREATED: _ClassVar[StorageEventType]
STORAGE_TYPE_UNSPECIFIED: StorageType
STORAGE_TYPE_GCS: StorageType
STORAGE_TYPE_S3: StorageType
STORAGE_TYPE_FS: StorageType
STORAGE_EVENT_TYPE_UNSPECIFIED: StorageEventType
STORAGE_EVENT_TYPE_CREATED: StorageEventType

class StorageLocation(_message.Message):
    __slots__ = ("id", "location", "type")
    ID_FIELD_NUMBER: _ClassVar[int]
    LOCATION_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    id: _core_pb2.UUID
    location: str
    type: StorageType
    def __init__(self, id: _Optional[_Union[_core_pb2.UUID, _Mapping]] = ..., location: _Optional[str] = ..., type: _Optional[_Union[StorageType, str]] = ...) -> None: ...

class StorageLocations(_message.Message):
    __slots__ = ("locations",)
    LOCATIONS_FIELD_NUMBER: _ClassVar[int]
    locations: _containers.RepeatedCompositeFieldContainer[StorageLocation]
    def __init__(self, locations: _Optional[_Iterable[_Union[StorageLocation, _Mapping]]] = ...) -> None: ...

class RecurrentTaskPrototype(_message.Message):
    __slots__ = ("id", "name", "prototype", "storage_event_triggers", "cron_triggers")
    ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    PROTOTYPE_FIELD_NUMBER: _ClassVar[int]
    STORAGE_EVENT_TRIGGERS_FIELD_NUMBER: _ClassVar[int]
    CRON_TRIGGERS_FIELD_NUMBER: _ClassVar[int]
    id: _core_pb2.UUID
    name: str
    prototype: _core_pb2.TaskSubmission
    storage_event_triggers: _containers.RepeatedCompositeFieldContainer[StorageEventTrigger]
    cron_triggers: _containers.RepeatedCompositeFieldContainer[CronTrigger]
    def __init__(self, id: _Optional[_Union[_core_pb2.UUID, _Mapping]] = ..., name: _Optional[str] = ..., prototype: _Optional[_Union[_core_pb2.TaskSubmission, _Mapping]] = ..., storage_event_triggers: _Optional[_Iterable[_Union[StorageEventTrigger, _Mapping]]] = ..., cron_triggers: _Optional[_Iterable[_Union[CronTrigger, _Mapping]]] = ...) -> None: ...

class RecurrentTasks(_message.Message):
    __slots__ = ("tasks",)
    TASKS_FIELD_NUMBER: _ClassVar[int]
    tasks: _containers.RepeatedCompositeFieldContainer[RecurrentTaskPrototype]
    def __init__(self, tasks: _Optional[_Iterable[_Union[RecurrentTaskPrototype, _Mapping]]] = ...) -> None: ...

class StorageEventTrigger(_message.Message):
    __slots__ = ("id", "storage_location", "glob_pattern")
    ID_FIELD_NUMBER: _ClassVar[int]
    STORAGE_LOCATION_FIELD_NUMBER: _ClassVar[int]
    GLOB_PATTERN_FIELD_NUMBER: _ClassVar[int]
    id: _core_pb2.UUID
    storage_location: StorageLocation
    glob_pattern: str
    def __init__(self, id: _Optional[_Union[_core_pb2.UUID, _Mapping]] = ..., storage_location: _Optional[_Union[StorageLocation, _Mapping]] = ..., glob_pattern: _Optional[str] = ...) -> None: ...

class CronTrigger(_message.Message):
    __slots__ = ("id", "schedule")
    ID_FIELD_NUMBER: _ClassVar[int]
    SCHEDULE_FIELD_NUMBER: _ClassVar[int]
    id: _core_pb2.UUID
    schedule: str
    def __init__(self, id: _Optional[_Union[_core_pb2.UUID, _Mapping]] = ..., schedule: _Optional[str] = ...) -> None: ...

class RecurrentTask(_message.Message):
    __slots__ = ("trigger_event", "args")
    TRIGGER_EVENT_FIELD_NUMBER: _ClassVar[int]
    ARGS_FIELD_NUMBER: _ClassVar[int]
    trigger_event: bytes
    args: bytes
    def __init__(self, trigger_event: _Optional[bytes] = ..., args: _Optional[bytes] = ...) -> None: ...

class TriggeredStorageEvent(_message.Message):
    __slots__ = ("storage_location_id", "type", "location")
    STORAGE_LOCATION_ID_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    LOCATION_FIELD_NUMBER: _ClassVar[int]
    storage_location_id: _core_pb2.UUID
    type: StorageEventType
    location: str
    def __init__(self, storage_location_id: _Optional[_Union[_core_pb2.UUID, _Mapping]] = ..., type: _Optional[_Union[StorageEventType, str]] = ..., location: _Optional[str] = ...) -> None: ...

class TriggeredCronEvent(_message.Message):
    __slots__ = ("trigger_time",)
    TRIGGER_TIME_FIELD_NUMBER: _ClassVar[int]
    trigger_time: _timestamp_pb2.Timestamp
    def __init__(self, trigger_time: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...
