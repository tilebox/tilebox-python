"""Compatibility imports for shared UUID conversions."""

from _tilebox.uuid import (
    as_uuid,
    must_uuid_to_uuid_message,
    uuid_message_to_optional_uuid,
    uuid_message_to_uuid,
    uuid_to_uuid_message,
)

__all__ = [
    "as_uuid",
    "must_uuid_to_uuid_message",
    "uuid_message_to_optional_uuid",
    "uuid_message_to_uuid",
    "uuid_to_uuid_message",
]
