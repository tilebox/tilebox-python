"""Resolved asset metadata for Tilebox datapoints."""

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import Any, TypeVar, cast

import numpy as np
import xarray as xr
from protobuf import Message
from typing_extensions import NotRequired, TypedDict

from tilebox.datasets.datasets.stac.v1.asset_metadata_pb import (
    ClassificationClass,
    EOCommonName,
    EOProperties,
    File,
    Projection,
    RasterProperties,
    RasterSampling,
    View,
)
from tilebox.datasets.datasets.stac.v1.asset_pb import (
    AssetAccessProfile,
    Assets,
    DataType,
    KnownAssetRole,
    Statistics,
)
from tilebox.datasets.datasets.stac.v1.asset_pb import (
    AssetLocation as ProtoAssetLocation,
)
from tilebox.datasets.datasets.stac.v1.asset_pb import (
    Band as ProtoBand,
)
from tilebox.datasets.datasets.stac.v1.authentication_pb import Authentication, AuthenticationScheme
from tilebox.datasets.datasets.stac.v1.core_pb import KnownMediaType, MediaType
from tilebox.datasets.datasets.stac.v1.product_pb import ProductProperties
from tilebox.datasets.datasets.stac.v1.sar_pb import (
    SARFrequencyBand,
    SARObservationDirection,
    SARProperties,
)
from tilebox.datasets.datasets.stac.v1.satellite_pb import SatelliteProperties
from tilebox.datasets.datasets.stac.v1.storage_pb import Storage, StorageScheme

_ASSETS_MESSAGE_NAME = "datasets.stac.v1.Assets"
_STORAGE_MESSAGE_NAME = "datasets.stac.v1.Storage"
_AUTHENTICATION_MESSAGE_NAME = "datasets.stac.v1.Authentication"
_EMPTY_MAPPING: Mapping[str, Any] = MappingProxyType({})
_MessageT = TypeVar("_MessageT", bound=Message[Any])
_MEDIA_TYPES = {
    KnownMediaType.GEOJSON: "application/geo+json",
    KnownMediaType.JSON: "application/json",
    KnownMediaType.CLOUD_OPTIMIZED_GEOTIFF: "image/tiff; application=geotiff; profile=cloud-optimized",
    KnownMediaType.JPEG_2000: "image/jp2",
    KnownMediaType.JPEG: "image/jpeg",
    KnownMediaType.PNG: "image/png",
    KnownMediaType.APPLICATION_XML: "application/xml",
    KnownMediaType.ZIP: "application/zip",
    KnownMediaType.DIRECTORY: "application/x-directory",
    KnownMediaType.GEOTIFF: "image/tiff; application=geotiff",
    KnownMediaType.TIFF: "image/tiff",
    KnownMediaType.HDF5: "application/x-hdf5",
    KnownMediaType.HDF: "application/x-hdf",
    KnownMediaType.NETCDF: "application/netcdf",
    KnownMediaType.ZARR_V2: "application/vnd.zarr; version=2",
    KnownMediaType.ZARR_V3: "application/vnd.zarr; version=3",
    KnownMediaType.PARQUET: "application/vnd.apache.parquet",
    KnownMediaType.GEOPACKAGE: "application/geopackage+sqlite3",
    KnownMediaType.COPC: "application/vnd.laszip+copc",
    KnownMediaType.HTML: "text/html",
    KnownMediaType.TEXT: "text/plain",
    KnownMediaType.TEXT_XML: "text/xml",
    KnownMediaType.FLATGEOBUF: "application/vnd.flatgeobuf",
    KnownMediaType.PMTILES: "application/vnd.pmtiles",
    KnownMediaType.NITF: "application/vnd.nitf",
    KnownMediaType.OCTET_STREAM: "application/octet-stream",
}


class AssetFieldOverrides(TypedDict):
    """Optional xarray variable names for ambiguous asset metadata fields."""

    assets: NotRequired[str]
    storage: NotRequired[str]
    authentication: NotRequired[str]


@dataclass(frozen=True, slots=True)
class Band:
    """Resolved band metadata with asset-level defaults inherited."""

    name: str | None = None
    description: str | None = None
    data_type: DataType = DataType.UNSPECIFIED
    nodata: float | None = None
    unit: str | None = None
    eo: EOProperties | None = None
    raster: RasterProperties | None = None
    classes: tuple[ClassificationClass, ...] = ()
    sar: SARProperties | None = None


@dataclass(frozen=True, slots=True)
class AssetLocation:
    """A resolved asset URL and its applicable generated access schemes."""

    href: str
    storage_schemes: Mapping[str, StorageScheme] = _EMPTY_MAPPING
    authentication_schemes: Mapping[str, AuthenticationScheme] = _EMPTY_MAPPING


@dataclass(frozen=True, slots=True)
class Asset:
    """A resolved asset inspired by the STAC Asset Object specification.

    See https://github.com/radiantearth/stac-spec/blob/master/item-spec/item-spec.md#asset-object.
    """

    key: str
    primary: AssetLocation
    alternates: Mapping[str, AssetLocation] = _EMPTY_MAPPING
    media_type: str | None = None
    title: str | None = None
    description: str | None = None
    roles: frozenset[KnownAssetRole | str] = frozenset()
    gsd: float | None = None
    bands: tuple[Band, ...] = ()
    data_type: DataType = DataType.UNSPECIFIED
    nodata: float | None = None
    statistics: Statistics | None = None
    unit: str | None = None
    eo: EOProperties | None = None
    raster: RasterProperties | None = None
    projection: Projection | None = None
    view: View | None = None
    classes: tuple[ClassificationClass, ...] = ()
    file: File | None = None
    sar: SARProperties | None = None
    satellite: SatelliteProperties | None = None
    product: ProductProperties | None = None


@dataclass(frozen=True, slots=True)
class AssetCollection(Mapping[str, Asset]):
    """Resolved assets belonging to exactly one dataset datapoint."""

    _assets: Mapping[str, Asset]

    @classmethod
    def from_datapoint(
        cls,
        datapoint: xr.Dataset,
        *,
        fields: AssetFieldOverrides | None = None,
    ) -> "AssetCollection":
        """Resolve the assets attached to one Tilebox dataset datapoint.

        Args:
            datapoint: A scalar :class:`xarray.Dataset`, typically one result selected
                from :meth:`tilebox.datasets.Dataset.query`. For a query containing
                multiple datapoints, iterate with
                :func:`tilebox.datasets.iter_datapoints` first.
            fields: Optional xarray variable names for the ``assets``, ``storage``,
                and ``authentication`` protobuf messages. Fields are normally found
                from their concrete protobuf-py classes; specify only entries needed
                to resolve ambiguous datasets.

        Returns:
            An immutable, mapping-like collection keyed by asset name.

        Raises:
            TypeError: If ``datapoint`` is not an xarray dataset.
            ValueError: If the input is not scalar or its protobuf fields cannot be
                discovered or resolved unambiguously.
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
        root = _discover_xarray_message(datapoint, Assets, _ASSETS_MESSAGE_NAME, overrides.get("assets"))
        if root is None:
            raise ValueError(f"no populated {_ASSETS_MESSAGE_NAME} field found in datapoint")
        storage = _discover_xarray_message(datapoint, Storage, _STORAGE_MESSAGE_NAME, overrides.get("storage"))
        authentication = _discover_xarray_message(
            datapoint,
            Authentication,
            _AUTHENTICATION_MESSAGE_NAME,
            overrides.get("authentication"),
        )
        return cls(_resolve_assets(root, storage, authentication))

    def __getitem__(self, key: str) -> Asset:
        return self._assets[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._assets)

    def __len__(self) -> int:
        return len(self._assets)


def _resolve_refs(
    registry: Mapping[str, _MessageT],
    refs: list[str],
    kind: str,
) -> Mapping[str, _MessageT]:
    resolved = {}
    for key in refs:
        if key not in registry:
            raise ValueError(f"asset references missing {kind} scheme {key!r}") from None
        resolved[key] = registry[key]
    return MappingProxyType(resolved)


def _location(
    source: ProtoAssetLocation,
    profiles: list[AssetAccessProfile],
    storage: Mapping[str, StorageScheme],
    authentication: Mapping[str, AuthenticationScheme],
    *,
    fallback_href: str | None = None,
) -> tuple[str, AssetLocation]:
    """Expand an access-profile reference into a URL and access metadata."""
    if not source.has_field("access_profile_index"):
        raise ValueError("asset location is missing its access profile index")
    index = source.access_profile_index
    if index >= len(profiles):
        raise ValueError(f"invalid asset access profile index: {index}")
    profile = profiles[index]
    suffix = source.href if source.has_field("href") else fallback_href
    if suffix is None:
        raise ValueError("asset location has no href and no primary href to inherit")
    return profile.alternate_key, AssetLocation(
        href=profile.base_href + suffix,
        storage_schemes=_resolve_refs(storage, profile.storage_refs, "storage"),
        authentication_schemes=_resolve_refs(authentication, profile.auth_refs, "authentication"),
    )


def _inherit_eo(child: EOProperties | None, parent: EOProperties | None) -> EOProperties | None:
    if child is None:
        return parent
    if parent is None:
        return child
    return EOProperties(
        common_name=child.common_name if child.common_name != EOCommonName.UNSPECIFIED else parent.common_name,
        center_wavelength=(
            child.center_wavelength
            if child.has_field("center_wavelength")
            else parent.center_wavelength
            if parent.has_field("center_wavelength")
            else None
        ),
        full_width_half_max=(
            child.full_width_half_max
            if child.has_field("full_width_half_max")
            else parent.full_width_half_max
            if parent.has_field("full_width_half_max")
            else None
        ),
        solar_illumination=(
            child.solar_illumination
            if child.has_field("solar_illumination")
            else parent.solar_illumination
            if parent.has_field("solar_illumination")
            else None
        ),
    )


def _media_type(source: MediaType | None) -> str | None:
    if source is None:
        return None
    if source.has_field("custom"):
        return source.custom
    return _MEDIA_TYPES.get(source.known)


def _inherit_raster(child: RasterProperties | None, parent: RasterProperties | None) -> RasterProperties | None:
    if child is None:
        return parent
    if parent is None:
        return child
    return RasterProperties(
        sampling=child.sampling if child.sampling != RasterSampling.UNSPECIFIED else parent.sampling,
        scale=child.scale if child.has_field("scale") else parent.scale if parent.has_field("scale") else None,
        offset=child.offset if child.has_field("offset") else parent.offset if parent.has_field("offset") else None,
        spatial_resolution=(
            child.spatial_resolution
            if child.has_field("spatial_resolution")
            else parent.spatial_resolution
            if parent.has_field("spatial_resolution")
            else None
        ),
    )


def _inherit_sar(child: SARProperties | None, parent: SARProperties | None) -> SARProperties | None:
    if child is None:
        return parent
    if parent is None:
        return child
    return SARProperties(
        polarizations=child.polarizations or parent.polarizations,
        instrument_mode=(
            child.instrument_mode
            if child.has_field("instrument_mode")
            else parent.instrument_mode
            if parent.has_field("instrument_mode")
            else None
        ),
        frequency_band=(
            child.frequency_band if child.frequency_band != SARFrequencyBand.UNSPECIFIED else parent.frequency_band
        ),
        center_frequency=(
            child.center_frequency
            if child.has_field("center_frequency")
            else parent.center_frequency
            if parent.has_field("center_frequency")
            else None
        ),
        bandwidth=(
            child.bandwidth
            if child.has_field("bandwidth")
            else parent.bandwidth
            if parent.has_field("bandwidth")
            else None
        ),
        resolution_range=(
            child.resolution_range
            if child.has_field("resolution_range")
            else parent.resolution_range
            if parent.has_field("resolution_range")
            else None
        ),
        resolution_azimuth=(
            child.resolution_azimuth
            if child.has_field("resolution_azimuth")
            else parent.resolution_azimuth
            if parent.has_field("resolution_azimuth")
            else None
        ),
        pixel_spacing_range=(
            child.pixel_spacing_range
            if child.has_field("pixel_spacing_range")
            else parent.pixel_spacing_range
            if parent.has_field("pixel_spacing_range")
            else None
        ),
        pixel_spacing_azimuth=(
            child.pixel_spacing_azimuth
            if child.has_field("pixel_spacing_azimuth")
            else parent.pixel_spacing_azimuth
            if parent.has_field("pixel_spacing_azimuth")
            else None
        ),
        looks_range=(
            child.looks_range
            if child.has_field("looks_range")
            else parent.looks_range
            if parent.has_field("looks_range")
            else None
        ),
        looks_azimuth=(
            child.looks_azimuth
            if child.has_field("looks_azimuth")
            else parent.looks_azimuth
            if parent.has_field("looks_azimuth")
            else None
        ),
        looks_equivalent_number=(
            child.looks_equivalent_number
            if child.has_field("looks_equivalent_number")
            else parent.looks_equivalent_number
            if parent.has_field("looks_equivalent_number")
            else None
        ),
        observation_direction=(
            child.observation_direction
            if child.observation_direction != SARObservationDirection.UNSPECIFIED
            else parent.observation_direction
        ),
        relative_burst=(
            child.relative_burst
            if child.has_field("relative_burst")
            else parent.relative_burst
            if parent.has_field("relative_burst")
            else None
        ),
        beam_ids=child.beam_ids or parent.beam_ids,
    )


def _resolve_band(source: ProtoBand, asset: Asset) -> Band:
    return Band(
        name=source.name if source.has_field("name") else None,
        description=source.description if source.has_field("description") else None,
        data_type=source.data_type if source.data_type != DataType.UNSPECIFIED else asset.data_type,
        nodata=source.nodata if source.has_field("nodata") else asset.nodata,
        unit=source.unit if source.has_field("unit") else asset.unit,
        eo=_inherit_eo(source.eo, asset.eo),
        raster=_inherit_raster(source.raster, asset.raster),
        classes=tuple(source.classes or asset.classes),
        sar=_inherit_sar(source.sar, asset.sar),
    )


def _resolve_assets(
    root: Assets,
    storage_message: Storage | None,
    authentication_message: Authentication | None,
) -> Mapping[str, Asset]:
    storage = storage_message.schemes if storage_message is not None else {}
    authentication = authentication_message.schemes if authentication_message is not None else {}
    result: dict[str, Asset] = {}
    for source in root.assets:
        if source.primary is None:
            raise ValueError(f"asset {source.key!r} has no primary location")
        primary_suffix = source.primary.href if source.primary.has_field("href") else None
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
        asset = Asset(
            key=source.key,
            primary=primary,
            alternates=MappingProxyType(alternates),
            media_type=_media_type(source.media_type),
            title=source.title if source.has_field("title") else None,
            description=source.description if source.has_field("description") else None,
            roles=frozenset([*source.roles, *source.custom_roles]),
            gsd=source.gsd if source.has_field("gsd") else None,
            data_type=source.data_type,
            nodata=source.nodata if source.has_field("nodata") else None,
            statistics=source.statistics,
            unit=source.unit if source.has_field("unit") else None,
            eo=source.eo,
            raster=source.raster,
            projection=source.projection,
            view=source.view,
            classes=tuple(source.classes),
            file=source.file,
            sar=source.sar,
            satellite=source.satellite,
            product=source.product,
        )
        bands = []
        for index in source.band_profile_indices:
            if index >= len(root.band_profiles):
                raise ValueError(f"invalid band profile index: {index}")
            bands.append(_resolve_band(root.band_profiles[index], asset))
        asset = replace(asset, bands=tuple(bands))
        if asset.key in result:
            raise ValueError(f"duplicate asset key: {asset.key!r}")
        result[asset.key] = asset
    return MappingProxyType(result)


def _message_values(data: Any) -> list[Message[Any]]:
    values = np.asarray(data.values, dtype=object).reshape(-1)
    return [value for value in values if isinstance(value, Message)]


def _discover_xarray_message(
    datapoint: xr.Dataset,
    message_type: type[_MessageT],
    message_name: str,
    variable_override: str | None,
) -> _MessageT | None:
    """Find one concrete protobuf-py message among the xarray variables."""
    if variable_override is not None:
        if variable_override not in datapoint.variables:
            raise ValueError(f"context field {variable_override!r} is not present in the datapoint")
        values = [value for value in _message_values(datapoint[variable_override]) if isinstance(value, message_type)]
        if len(values) != 1:
            raise ValueError(f"field {variable_override!r} does not contain exactly one {message_name} message")
        return cast(_MessageT, values[0])
    candidates = []
    for name, data in datapoint.variables.items():
        values = [value for value in _message_values(data) if isinstance(value, message_type)]
        if values:
            if len(values) != 1:
                raise ValueError(f"field {name!r} contains multiple {message_name} messages")
            candidates.append((name, values[0]))
    if len(candidates) > 1:
        raise ValueError(f"ambiguous {message_name} fields: {', '.join(name for name, _ in candidates)}")
    return cast(_MessageT, candidates[0][1]) if candidates else None
