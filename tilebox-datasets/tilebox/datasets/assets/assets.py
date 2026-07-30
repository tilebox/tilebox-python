"""Immutable asset metadata decoded from Tilebox datapoints."""

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, fields, replace
from types import MappingProxyType
from typing import Any, TypeVar, cast

import numpy as np
import xarray as xr
from google.protobuf.message import Message
from typing_extensions import NotRequired, TypedDict

from tilebox.datasets.assets.converters import _enum_name, _has_field, converters
from tilebox.datasets.assets.stac.authentication import AuthenticationScheme
from tilebox.datasets.assets.stac.metadata import (
    ClassificationClass,
    ElectroOpticalProperties,
    File,
    Projection,
    RasterProperties,
    Statistics,
    View,
)
from tilebox.datasets.assets.stac.product import ProductProperties
from tilebox.datasets.assets.stac.sar import SarProperties
from tilebox.datasets.assets.stac.satellite import SatelliteProperties
from tilebox.datasets.assets.stac.storage import StorageScheme
from tilebox.datasets.datasets.stac.v1.asset_pb2 import Assets
from tilebox.datasets.datasets.stac.v1.asset_pb2 import Band as BandProto
from tilebox.datasets.datasets.stac.v1.authentication_pb2 import Authentication
from tilebox.datasets.datasets.stac.v1.storage_pb2 import Storage

_ASSETS_MESSAGE_NAME = Assets.DESCRIPTOR.full_name
_STORAGE_MESSAGE_NAME = Storage.DESCRIPTOR.full_name
_AUTHENTICATION_MESSAGE_NAME = Authentication.DESCRIPTOR.full_name
_EMPTY_MAPPING: Mapping[str, Any] = MappingProxyType({})
_MessageT = TypeVar("_MessageT", bound=Message)


class AssetFieldOverrides(TypedDict):
    """Optional xarray variable names for ambiguous asset metadata fields."""

    assets: NotRequired[str]
    storage: NotRequired[str]
    authentication: NotRequired[str]


@dataclass(frozen=True, slots=True)
class Band:
    """Band metadata inspired by the STAC asset and extension specifications."""

    name: str | None = None
    description: str | None = None
    data_type: str = "unspecified"
    nodata: float | None = None
    unit: str | None = None
    electro_optical: ElectroOpticalProperties | None = None
    raster: RasterProperties | None = None
    classes: tuple[ClassificationClass, ...] = ()
    sar: SarProperties | None = None


@dataclass(frozen=True, slots=True)
class AssetLocation:
    """A resolved asset URL and its applicable access schemes."""

    href: str
    storage_schemes: Mapping[str, StorageScheme] = _EMPTY_MAPPING
    authentication_schemes: Mapping[str, AuthenticationScheme] = _EMPTY_MAPPING


@dataclass(frozen=True, slots=True)
class Asset:
    """An immutable asset inspired by the STAC Asset Object specification.

    See https://github.com/radiantearth/stac-spec/blob/master/item-spec/item-spec.md#asset-object.
    """

    key: str
    primary: AssetLocation
    alternates: Mapping[str, AssetLocation] = _EMPTY_MAPPING
    media_type: str | None = None
    title: str | None = None
    description: str | None = None
    roles: frozenset[str] = frozenset()
    gsd: float | None = None
    bands: tuple[Band, ...] = ()
    data_type: str = "unspecified"
    nodata: float | None = None
    statistics: Statistics | None = None
    unit: str | None = None
    electro_optical: ElectroOpticalProperties | None = None
    raster: RasterProperties | None = None
    projection: Projection | None = None
    view: View | None = None
    classes: tuple[ClassificationClass, ...] = ()
    file: File | None = None
    sar: SarProperties | None = None
    satellite: SatelliteProperties | None = None
    product: ProductProperties | None = None


@dataclass(frozen=True, slots=True)
class AssetCollection(Mapping[str, Asset]):
    """Immutable assets belonging to exactly one dataset datapoint."""

    _assets: Mapping[str, Asset]

    @classmethod
    def from_datapoint(
        cls,
        datapoint: xr.Dataset,
        *,
        fields: AssetFieldOverrides | None = None,
    ) -> "AssetCollection":
        """Decode the assets attached to one Tilebox dataset datapoint.

        Args:
            datapoint: A scalar :class:`xarray.Dataset`, typically one result selected
                from :meth:`tilebox.datasets.Dataset.query`. For a query containing
                multiple datapoints, iterate with
                :func:`tilebox.datasets.iter_datapoints` first.
            fields: Optional xarray variable names for the ``assets``, ``storage``,
                and ``authentication`` protobuf messages. Fields are normally
                discovered from their generated protobuf types; specify only the
                entries needed to resolve ambiguous datasets.

        Returns:
            An immutable, mapping-like collection keyed by asset name.

        Raises:
            TypeError: If ``datapoint`` is not an xarray dataset.
            ValueError: If the input is not scalar or its protobuf fields cannot be
                discovered or decoded unambiguously.
        """
        if not isinstance(datapoint, xr.Dataset):
            raise TypeError("datapoint must be an xarray.Dataset")
        if datapoint.sizes.get("time", 0) > 1:
            dimension = "time"
            size = datapoint.sizes[dimension]
            raise ValueError(
                f"AssetCollection.from_datapoint() expects one datapoint, but received {size} "
                f"along dimension {dimension!r}.\n\n"
                f"Select one explicitly:\n\n    assets = AssetCollection.from_datapoint(data.isel({dimension}=0))\n\n"
                "Or iterate over all datapoints:\n\n"
                "    for datapoint in iter_datapoints(data):\n"
                "        assets = AssetCollection.from_datapoint(datapoint)"
            )
        overrides = fields or {}
        root = _discover_xarray_message(datapoint, Assets, overrides.get("assets"))
        if root is None:
            raise ValueError(f"no populated {_ASSETS_MESSAGE_NAME} field found in datapoint")
        storage = _discover_xarray_message(datapoint, Storage, overrides.get("storage"))
        authentication = _discover_xarray_message(datapoint, Authentication, overrides.get("authentication"))
        return cls(_decode_assets(root, storage, authentication))

    def __getitem__(self, key: str) -> Asset:
        return self._assets[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._assets)

    def __len__(self) -> int:
        return len(self._assets)


_MEDIA_TYPES = {
    "geojson": "application/geo+json",
    "json": "application/json",
    "cloud_optimized_geotiff": "image/tiff; application=geotiff; profile=cloud-optimized",
    "jpeg_2000": "image/jp2",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "application_xml": "application/xml",
    "zip": "application/zip",
    "directory": "inode/directory",
    "geotiff": "image/tiff; application=geotiff",
    "tiff": "image/tiff",
    "hdf5": "application/x-hdf5",
    "hdf": "application/x-hdf",
    "netcdf": "application/x-netcdf",
    "zarr_v2": "application/vnd+zarr",
    "zarr_v3": "application/vnd+zarr",
    "parquet": "application/vnd.apache.parquet",
    "geopackage": "application/geopackage+sqlite3",
    "copc": "application/vnd.laszip+copc",
    "html": "text/html",
    "text": "text/plain",
    "text_xml": "text/xml",
    "flatgeobuf": "application/vnd.flatgeobuf",
    "pmtiles": "application/vnd.pmtiles",
    "nitf": "image/nitf",
    "octet_stream": "application/octet-stream",
}


def _convert_storage(key: str, message: Message) -> StorageScheme:
    return replace(converters.convert(message), key=key)


def _convert_authentication(key: str, message: Message) -> AuthenticationScheme:
    return replace(converters.convert(message), key=key)


def _resolve_refs(registry: Mapping[str, Any], refs: Any, kind: str) -> Mapping[str, Any]:
    resolved = {}
    for key in refs:
        if key not in registry:
            raise ValueError(f"asset references missing {kind} scheme {key!r}") from None
        resolved[key] = registry[key]
    return MappingProxyType(resolved)


def _location(
    source: Any,
    profiles: Any,
    storage: Mapping[str, StorageScheme],
    authentication: Mapping[str, AuthenticationScheme],
    *,
    fallback_href: str | None = None,
) -> tuple[str, AssetLocation]:
    """Resolve a compact protobuf location through its shared access profile.

    Access profiles deduplicate URL prefixes and scheme references in protobuf. This
    expands one profile index into a complete URL and keyed scheme mappings. Alternate
    locations may inherit the primary location's relative href through ``fallback_href``.
    """
    if not _has_field(source, "access_profile_index"):
        raise ValueError("asset location is missing its access profile index")
    index = source.access_profile_index
    if index >= len(profiles):
        raise ValueError(f"invalid asset access profile index: {index}")
    profile = profiles[index]
    suffix = source.href if _has_field(source, "href") else fallback_href
    if suffix is None:
        raise ValueError("asset location has no href and no primary href to inherit")
    return profile.alternate_key, AssetLocation(
        href=profile.base_href + suffix,
        storage_schemes=_resolve_refs(storage, profile.storage_refs, "storage"),
        authentication_schemes=_resolve_refs(authentication, profile.auth_refs, "authentication"),
    )


def _inherit(child: Any, parent: Any) -> Any:
    """Fill unspecified band metadata from its asset-level defaults.

    STAC permits common metadata to be attached to the asset while individual bands
    override only selected fields. This creates the effective immutable band model.
    """
    if child is None:
        return parent
    if parent is None:
        return child
    values = {}
    for item in fields(child):
        value = getattr(child, item.name)
        if value is None or value in ("unspecified", ()):
            values[item.name] = getattr(parent, item.name)
    return replace(child, **values)


def _decode_band(source: BandProto, asset: Asset) -> Band:
    band = Band(
        name=source.name if _has_field(source, "name") else None,
        description=source.description if _has_field(source, "description") else None,
        data_type=_enum_name(source.DESCRIPTOR.fields_by_name["data_type"], source.data_type),
        nodata=source.nodata if _has_field(source, "nodata") else None,
        unit=source.unit if _has_field(source, "unit") else None,
        electro_optical=converters.convert(source.eo) if source.HasField("eo") else None,
        raster=converters.convert(source.raster) if source.HasField("raster") else None,
        classes=tuple(converters.convert(item) for item in source.classes),
        sar=converters.convert(source.sar) if source.HasField("sar") else None,
    )
    return replace(
        band,
        data_type=asset.data_type if band.data_type == "unspecified" else band.data_type,
        nodata=asset.nodata if band.nodata is None else band.nodata,
        unit=asset.unit if band.unit is None else band.unit,
        electro_optical=_inherit(band.electro_optical, asset.electro_optical),
        raster=_inherit(band.raster, asset.raster),
        classes=asset.classes if not band.classes else band.classes,
        sar=_inherit(band.sar, asset.sar),
    )


def _media_type(message: Message) -> str | None:
    if _has_field(message, "custom"):
        return message.custom  # type: ignore[attr-defined]
    known = _enum_name(message.DESCRIPTOR.fields_by_name["known"], message.known)  # type: ignore[attr-defined]
    return None if known == "unspecified" else _MEDIA_TYPES[known]


def _decode_assets(
    root: Assets, storage_message: Storage | None, authentication_message: Authentication | None
) -> Mapping[str, Asset]:
    storage = (
        {key: _convert_storage(key, value) for key, value in storage_message.schemes.items()}
        if storage_message is not None
        else {}
    )
    authentication = (
        {key: _convert_authentication(key, value) for key, value in authentication_message.schemes.items()}
        if authentication_message is not None
        else {}
    )
    result: dict[str, Asset] = {}
    for source in root.assets:
        if not source.HasField("primary"):
            raise ValueError(f"asset {source.key!r} has no primary location")
        primary_suffix = source.primary.href if _has_field(source.primary, "href") else None
        _, primary = _location(source.primary, root.access_profiles, storage, authentication)
        alternates: dict[str, AssetLocation] = {}
        for alternate_source in source.alternates:
            alternate_key, alternate = _location(
                alternate_source,
                root.access_profiles,
                storage,
                authentication,
                fallback_href=primary_suffix,
            )
            if not alternate_key:
                raise ValueError(f"asset {source.key!r} has an alternate with an empty key")
            if alternate_key in alternates:
                raise ValueError(f"asset {source.key!r} has duplicate alternate key {alternate_key!r}")
            alternates[alternate_key] = alternate
        role_field = source.DESCRIPTOR.fields_by_name["roles"]
        asset = Asset(
            key=source.key,
            primary=primary,
            alternates=MappingProxyType(alternates),
            media_type=_media_type(source.media_type) if source.HasField("media_type") else None,
            title=source.title if _has_field(source, "title") else None,
            description=source.description if _has_field(source, "description") else None,
            roles=frozenset([*(_enum_name(role_field, role) for role in source.roles), *source.custom_roles]),
            gsd=source.gsd if _has_field(source, "gsd") else None,
            data_type=_enum_name(source.DESCRIPTOR.fields_by_name["data_type"], source.data_type),
            nodata=source.nodata if _has_field(source, "nodata") else None,
            statistics=converters.convert(source.statistics) if source.HasField("statistics") else None,
            unit=source.unit if _has_field(source, "unit") else None,
            electro_optical=converters.convert(source.eo) if source.HasField("eo") else None,
            raster=converters.convert(source.raster) if source.HasField("raster") else None,
            projection=converters.convert(source.projection) if source.HasField("projection") else None,
            view=converters.convert(source.view) if source.HasField("view") else None,
            classes=tuple(converters.convert(item) for item in source.classes),
            file=converters.convert(source.file) if source.HasField("file") else None,
            sar=converters.convert(source.sar) if source.HasField("sar") else None,
            satellite=converters.convert(source.satellite) if source.HasField("satellite") else None,
            product=converters.convert(source.product) if source.HasField("product") else None,
        )
        bands = []
        for index in source.band_profile_indices:
            if index >= len(root.band_profiles):
                raise ValueError(f"invalid band profile index: {index}")
            bands.append(_decode_band(root.band_profiles[index], asset))
        asset = replace(asset, bands=tuple(bands))
        if asset.key in result:
            raise ValueError(f"duplicate asset key: {asset.key!r}")
        result[asset.key] = asset
    return MappingProxyType(result)


def _message_values(data: Any) -> list[Message]:
    values = np.asarray(data.values, dtype=object).reshape(-1)
    return [value for value in values if isinstance(value, Message)]


def _discover_xarray_message(
    datapoint: xr.Dataset,
    message_type: type[_MessageT],
    variable_override: str | None,
) -> _MessageT | None:
    """Find one protobuf message in xarray variables by generated class.

    ``variable_override`` selects an exact xarray variable when descriptor discovery
    would be ambiguous. The descriptor full name is a fallback for messages created
    from an equivalent dynamic descriptor pool, whose generated Python class differs.
    """
    message_name = message_type.DESCRIPTOR.full_name

    def matches(value: Message) -> bool:
        return isinstance(value, message_type) or value.DESCRIPTOR.full_name == message_name

    if variable_override is not None:
        if variable_override not in datapoint.variables:
            raise ValueError(f"context field {variable_override!r} is not present in the datapoint")
        values = [value for value in _message_values(datapoint[variable_override]) if matches(value)]
        if len(values) != 1:
            raise ValueError(f"field {variable_override!r} does not contain exactly one {message_name} message")
        return cast(_MessageT, values[0])
    candidates = []
    for name, data in datapoint.variables.items():
        values = [value for value in _message_values(data) if matches(value)]
        if values:
            if len(values) != 1:
                raise ValueError(f"field {name!r} contains multiple {message_name} messages")
            candidates.append((name, values[0]))
    if len(candidates) > 1:
        raise ValueError(f"ambiguous {message_name} fields: {', '.join(name for name, _ in candidates)}")
    return cast(_MessageT, candidates[0][1]) if candidates else None
