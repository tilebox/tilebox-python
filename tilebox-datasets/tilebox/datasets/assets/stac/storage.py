"""Immutable model inspired by the STAC storage extension.

See https://github.com/stac-extensions/storage.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from tilebox.datasets.assets.converters import converters
from tilebox.datasets.datasets.stac.v1.storage_pb2 import StorageScheme as StorageSchemeProto


@converters.register(
    StorageSchemeProto,
    rename_fields={"known_type": "type", "custom_type": "type"},
)
@dataclass(frozen=True, slots=True)
class StorageScheme:
    key: str = ""
    type: str | None = None
    platform: str | None = None
    title: str | None = None
    description: str | None = None
    region: str | None = None
    requester_pays: bool | None = None
    storage_class: str | None = None
    bucket: str | None = None
    account: str | None = None
    additional_properties: Mapping[str, Any] = MappingProxyType({})
