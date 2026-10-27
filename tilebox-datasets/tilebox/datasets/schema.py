"""Public Python field types supported in Tilebox dataset schemas.

Use these classes as the ``type`` in a field passed to
``Client.create_or_update_dataset()``, for example
``{"name": "assets", "type": Assets}``.
"""

from typing import TypeAlias
from uuid import UUID

from protobuf import Message
from shapely import Geometry

from tilebox.datasets.stac.v1.asset_pb import Assets
from tilebox.datasets.stac.v1.authentication_pb import Authentication
from tilebox.datasets.stac.v1.core_pb import Links, Provider
from tilebox.datasets.stac.v1.processing_pb import ProcessingSoftware
from tilebox.datasets.stac.v1.storage_pb import Storage

MessageFieldType: TypeAlias = (
    type[Assets]
    | type[list[Assets]]
    | type[Authentication]
    | type[list[Authentication]]
    | type[Links]
    | type[list[Links]]
    | type[Provider]
    | type[list[Provider]]
    | type[ProcessingSoftware]
    | type[list[ProcessingSoftware]]
    | type[Storage]
    | type[list[Storage]]
)
"""A generated message class supported as a scalar or repeated dataset field."""

_MESSAGE_FIELD_TYPES = (Assets, Authentication, Links, Provider, ProcessingSoftware, Storage)


def _message_field_type(value_type: object) -> type[Message] | None:
    """Return a supported native message class."""
    for message_type in _MESSAGE_FIELD_TYPES:
        if value_type is message_type:
            return message_type
    return None


__all__ = [
    "UUID",
    "Assets",
    "Authentication",
    "Geometry",
    "Links",
    "MessageFieldType",
    "ProcessingSoftware",
    "Provider",
    "Storage",
]
