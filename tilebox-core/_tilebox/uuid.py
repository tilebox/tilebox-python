# allow the uuid module name which shadows the builtin:
from typing import Protocol
from uuid import UUID

from _tilebox.proto.tilebox.v1 import id_pb

_NIL_UUID = UUID(int=0)


class _UUIDMessage(Protocol):
    @property
    def uuid(self) -> bytes: ...


def uuid_message_to_uuid(uuid_message: _UUIDMessage | None) -> UUID:
    if uuid_message is None or uuid_message.uuid == b"":
        return _NIL_UUID
    return UUID(bytes=uuid_message.uuid)


def uuid_message_to_optional_uuid(uuid_message: _UUIDMessage | None) -> UUID | None:
    if uuid_message is None:
        return None
    if uuid_message.uuid == b"":
        return None
    return UUID(bytes=uuid_message.uuid)


def uuid_to_uuid_message(uuid: UUID | None) -> id_pb.ID | None:
    if uuid is None or uuid == _NIL_UUID:
        return None
    return id_pb.ID(uuid=uuid.bytes)


def must_uuid_to_uuid_message(uuid: UUID) -> id_pb.ID:
    if uuid == _NIL_UUID:
        raise ValueError("UUID must not be Nil")
    return id_pb.ID(uuid=uuid.bytes)


def as_uuid(uuid: str | UUID) -> UUID:
    if isinstance(uuid, str):
        return UUID(uuid)
    return uuid
