from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional

DESCRIPTOR: _descriptor.FileDescriptor

class ProcessingSoftware(_message.Message):
    __slots__ = ("versions",)
    class VersionsEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: str
        def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...
    VERSIONS_FIELD_NUMBER: _ClassVar[int]
    versions: _containers.ScalarMap[str, str]
    def __init__(self, versions: _Optional[_Mapping[str, str]] = ...) -> None: ...
