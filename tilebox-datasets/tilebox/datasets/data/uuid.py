# allow the uuid module name which shadows the builtin: # noqa: A005
from uuid import UUID

from tilebox.datasets.datasetsv1 import core_pb2

_NIL_UUID = UUID(int=0)


def uuid_message_to_uuid(uuid_message: core_pb2.ID) -> UUID:
    if uuid_message.uuid == b"":
        return _NIL_UUID
    return UUID(bytes=uuid_message.uuid)


def uuid_message_to_optional_uuid(uuid_message: core_pb2.ID) -> UUID | None:
    if uuid_message.uuid == b"":
        return None
    return UUID(bytes=uuid_message.uuid)


def uuid_to_uuid_message(uuid: UUID | None) -> core_pb2.ID | None:
    if uuid is None or uuid == _NIL_UUID:
        return None
    return core_pb2.ID(uuid=uuid.bytes)
