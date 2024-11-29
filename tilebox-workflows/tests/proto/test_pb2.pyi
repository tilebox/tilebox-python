from typing import ClassVar as _ClassVar

from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message

DESCRIPTOR: _descriptor.FileDescriptor

class SampleArgs(_message.Message):
    __slots__ = ("some_int", "some_string")
    SOME_STRING_FIELD_NUMBER: _ClassVar[int]
    SOME_INT_FIELD_NUMBER: _ClassVar[int]
    some_string: str
    some_int: int
    def __init__(self, some_string: str | None = ..., some_int: int | None = ...) -> None: ...
