from google.protobuf import empty_pb2 as _empty_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from tilebox.datasets.tilebox.v1 import id_pb2 as _id_pb2
from tilebox.workflows.workflows.v1 import core_pb2 as _core_pb2
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
    id: _id_pb2.ID
    location: str
    type: StorageType
    def __init__(self, id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ..., location: _Optional[str] = ..., type: _Optional[_Union[StorageType, str]] = ...) -> None: ...

class StorageLocations(_message.Message):
    __slots__ = ("locations",)
    LOCATIONS_FIELD_NUMBER: _ClassVar[int]
    locations: _containers.RepeatedCompositeFieldContainer[StorageLocation]
    def __init__(self, locations: _Optional[_Iterable[_Union[StorageLocation, _Mapping]]] = ...) -> None: ...

class AutomationPrototype(_message.Message):
    __slots__ = ("id", "name", "prototype", "storage_event_triggers", "cron_triggers")
    ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    PROTOTYPE_FIELD_NUMBER: _ClassVar[int]
    STORAGE_EVENT_TRIGGERS_FIELD_NUMBER: _ClassVar[int]
    CRON_TRIGGERS_FIELD_NUMBER: _ClassVar[int]
    id: _id_pb2.ID
    name: str
    prototype: _core_pb2.TaskSubmission
    storage_event_triggers: _containers.RepeatedCompositeFieldContainer[StorageEventTrigger]
    cron_triggers: _containers.RepeatedCompositeFieldContainer[CronTrigger]
    def __init__(self, id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ..., name: _Optional[str] = ..., prototype: _Optional[_Union[_core_pb2.TaskSubmission, _Mapping]] = ..., storage_event_triggers: _Optional[_Iterable[_Union[StorageEventTrigger, _Mapping]]] = ..., cron_triggers: _Optional[_Iterable[_Union[CronTrigger, _Mapping]]] = ...) -> None: ...

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
    storage_location: StorageLocation
    glob_pattern: str
    def __init__(self, id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ..., storage_location: _Optional[_Union[StorageLocation, _Mapping]] = ..., glob_pattern: _Optional[str] = ...) -> None: ...

class CronTrigger(_message.Message):
    __slots__ = ("id", "schedule")
    ID_FIELD_NUMBER: _ClassVar[int]
    SCHEDULE_FIELD_NUMBER: _ClassVar[int]
    id: _id_pb2.ID
    schedule: str
    def __init__(self, id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ..., schedule: _Optional[str] = ...) -> None: ...

class Automation(_message.Message):
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
    storage_location_id: _id_pb2.ID
    type: StorageEventType
    location: str
    def __init__(self, storage_location_id: _Optional[_Union[_id_pb2.ID, _Mapping]] = ..., type: _Optional[_Union[StorageEventType, str]] = ..., location: _Optional[str] = ...) -> None: ...

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
