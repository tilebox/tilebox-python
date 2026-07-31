"""Public Python field types supported in Tilebox dataset schemas.

Use these classes as the ``type`` in a field passed to
``Client.create_or_update_dataset()``, for example
``{"name": "assets", "type": Assets}``.
"""

from typing import Any, TypeAlias, cast
from uuid import UUID

from google.protobuf.message import Message as WireMessage
from protobuf import Message
from shapely import Geometry

from tilebox.datasets.datasets.stac.v1.asset_pb import Assets
from tilebox.datasets.datasets.stac.v1.asset_pb2 import Assets as AssetsWire
from tilebox.datasets.datasets.stac.v1.authentication_pb import Authentication
from tilebox.datasets.datasets.stac.v1.authentication_pb2 import Authentication as AuthenticationWire
from tilebox.datasets.datasets.stac.v1.core_pb import Links, Provider
from tilebox.datasets.datasets.stac.v1.core_pb2 import Links as LinksWire
from tilebox.datasets.datasets.stac.v1.core_pb2 import Provider as ProviderWire
from tilebox.datasets.datasets.stac.v1.processing_pb import ProcessingSoftware
from tilebox.datasets.datasets.stac.v1.processing_pb2 import ProcessingSoftware as ProcessingSoftwareWire
from tilebox.datasets.datasets.stac.v1.storage_pb import Storage
from tilebox.datasets.datasets.stac.v1.storage_pb2 import Storage as StorageWire

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

_MESSAGE_FIELD_TYPES: dict[type[Message[Any]], type[WireMessage]] = {
    Assets: AssetsWire,
    Authentication: AuthenticationWire,
    Links: LinksWire,
    Provider: ProviderWire,
    ProcessingSoftware: ProcessingSoftwareWire,
    Storage: StorageWire,
}


def _wire_message_type(value_type: object) -> type[WireMessage] | None:
    """Return the wire class for a supported public message class."""
    return _MESSAGE_FIELD_TYPES.get(cast("type[Message[Any]]", value_type))


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
