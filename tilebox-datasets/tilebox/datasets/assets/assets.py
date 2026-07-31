"""Semantic asset metadata authoring, compilation, and resolution."""

from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, is_dataclass, replace
from dataclasses import fields as dataclass_fields
from enum import Enum
from math import isnan
from types import MappingProxyType
from typing import Any, Literal, TypeVar, cast, overload

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
    Asset as ProtoAsset,
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
from tilebox.datasets.datasets.stac.v1.core_pb import KnownMediaType
from tilebox.datasets.datasets.stac.v1.core_pb import MediaType as ProtoMediaType
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
_NO_COMMON = object()
_MessageT = TypeVar("_MessageT", bound=Message[Any])


# Replace this compatibility definition with enum.StrEnum once Python 3.10 support is dropped.
class MediaType(str, Enum):
    """Common media types used by STAC assets and links."""

    GEOJSON = "application/geo+json"
    JSON = "application/json"
    CLOUD_OPTIMIZED_GEOTIFF = "image/tiff; application=geotiff; profile=cloud-optimized"
    JPEG_2000 = "image/jp2"
    JPEG = "image/jpeg"
    PNG = "image/png"
    APPLICATION_XML = "application/xml"
    ZIP = "application/zip"
    DIRECTORY = "application/x-directory"
    GEOTIFF = "image/tiff; application=geotiff"
    TIFF = "image/tiff"
    HDF5 = "application/x-hdf5"
    HDF = "application/x-hdf"
    NETCDF = "application/netcdf"
    ZARR_V2 = "application/vnd.zarr; version=2"
    ZARR_V3 = "application/vnd.zarr; version=3"
    PARQUET = "application/vnd.apache.parquet"
    GEOPACKAGE = "application/geopackage+sqlite3"
    COPC = "application/vnd.laszip+copc"
    HTML = "text/html"
    TEXT = "text/plain"
    TEXT_XML = "text/xml"
    FLATGEOBUF = "application/vnd.flatgeobuf"
    PMTILES = "application/vnd.pmtiles"
    NITF = "application/vnd.nitf"
    OCTET_STREAM = "application/octet-stream"

    def __str__(self) -> str:
        """Return the media-type value, matching enum.StrEnum semantics."""
        return self.value


_MEDIA_TYPES = {known: MediaType[known.name] for known in KnownMediaType if known != KnownMediaType.UNSPECIFIED}
_KNOWN_ROLES = {
    role.name.lower().replace("_", "-"): role for role in KnownAssetRole if role != KnownAssetRole.UNSPECIFIED
}
_ASSET_FIELD_DEFAULTS = {"assets": "assets", "storage": "storage", "authentication": "authentication"}
_SAR_FIELDS = (
    "polarizations",
    "instrument_mode",
    "frequency_band",
    "center_frequency",
    "bandwidth",
    "resolution_range",
    "resolution_azimuth",
    "pixel_spacing_range",
    "pixel_spacing_azimuth",
    "looks_range",
    "looks_azimuth",
    "looks_equivalent_number",
    "observation_direction",
    "relative_burst",
    "beam_ids",
)
_SAR_ENUM_DEFAULTS = {
    "frequency_band": SARFrequencyBand.UNSPECIFIED,
    "observation_direction": SARObservationDirection.UNSPECIFIED,
}
_RegistryAttribute = Literal["storage_schemes", "authentication_schemes"]


@dataclass(frozen=True, slots=True)
class _AccessProfileSpec:
    """Canonical values used to build and reference one access profile."""

    alternate_key: str
    default_alternate_name: str | None
    base_href: str
    storage_refs: tuple[str, ...]
    authentication_refs: tuple[str, ...]


class AssetFieldNames(TypedDict):
    """Dataset field names used to read or write asset metadata.

    Attributes:
        assets: Field containing the generated :class:`Assets` message.
        storage: Field containing the generated :class:`Storage` registry.
        authentication: Field containing the generated :class:`Authentication`
            registry.
    """

    assets: NotRequired[str]
    storage: NotRequired[str]
    authentication: NotRequired[str]


class AssetFields(TypedDict):
    """Compiled fields produced with the default asset field names."""

    assets: Assets
    storage: NotRequired[Storage]
    authentication: NotRequired[Authentication]


@dataclass(frozen=True, slots=True)
class Band:
    """Semantic metadata for one asset band.

    Asset-level defaults are inherited when an :class:`AssetCollection` is
    constructed.

    Attributes:
        name: Band name.
        description: Human-readable band description.
        data_type: Raster data type, or ``UNSPECIFIED`` to inherit it.
        nodata: Nodata value, or ``None`` to inherit it.
        unit: Unit name, or ``None`` to inherit it.
        eo: Generated Electro-Optical metadata.
        raster: Generated Raster extension metadata.
        classes: Generated Classification extension classes.
        sar: Generated Synthetic-Aperture Radar metadata.
    """

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
    """An asset URL and its applicable access schemes.

    Attributes:
        href: Fully resolved asset href.
        storage_schemes: Storage registry entries used by this location, keyed
            by their exact STAC registry keys.
        authentication_schemes: Authentication registry entries used by this
            location, keyed by their exact STAC registry keys.
        alternate_name: STAC alternate-assets display name.
    """

    href: str
    storage_schemes: Mapping[str, StorageScheme] = _EMPTY_MAPPING
    authentication_schemes: Mapping[str, AuthenticationScheme] = _EMPTY_MAPPING
    alternate_name: str | None = None


@dataclass(frozen=True, slots=True)
class Asset:
    """A semantic asset inspired by the STAC Asset Object specification.

    See https://github.com/radiantearth/stac-spec/blob/master/item-spec/item-spec.md#asset-object.

    Attributes:
        key: Key in the STAC assets object.
        primary: Primary asset location.
        alternates: Alternate locations keyed by their STAC alternate-assets key.
        media_type: Exact media type string.
        title: Optional title.
        description: Optional description.
        roles: Known or custom STAC asset roles.
        gsd: Ground sample distance in metres.
        bands: Ordered, resolved band metadata.
        data_type: Asset-level raster data type.
        nodata: Asset-level nodata value.
        statistics: Generated Raster statistics.
        unit: Asset-level unit.
        eo: Generated Electro-Optical metadata.
        raster: Generated Raster extension metadata.
        projection: Generated Projection extension metadata.
        view: Generated View extension metadata.
        classes: Generated Classification extension classes.
        file: Generated File extension metadata.
        sar: Generated Synthetic-Aperture Radar metadata.
        satellite: Generated Satellite extension metadata.
        product: Generated Product extension metadata.
    """

    key: str
    primary: AssetLocation
    alternates: Mapping[str, AssetLocation] = _EMPTY_MAPPING
    media_type: MediaType | str | None = None
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
class AssetCollection(Mapping[str, Asset]):  # noqa: PLW1641 - mutable mappings make the value unhashable
    """Semantic assets belonging to exactly one dataset datapoint.

    Use :meth:`from_assets` to construct and validate a semantic collection,
    :meth:`to_fields` to compile it into optimized ingestion fields, and
    :meth:`from_datapoint` to resolve optimized fields back into a semantic
    collection.
    """

    _assets: Mapping[str, Asset]

    @classmethod
    def from_datapoint(
        cls,
        datapoint: xr.Dataset,
        *,
        fields: AssetFieldNames | None = None,
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
            A read-only, mapping-like collection keyed by asset name.

        Raises:
            TypeError: If ``datapoint`` is not an xarray dataset or a configured
                field name is not a string.
            ValueError: If the input is not scalar or its protobuf fields cannot be
                discovered, validated, or resolved unambiguously.
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
        overrides = _validate_field_names(fields)
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

    @classmethod
    def from_assets(cls, assets: Iterable[Asset]) -> "AssetCollection":
        """Construct, validate, and normalize a semantic asset collection.

        Known role strings are canonicalized, Band values inherit Asset
        defaults, empty Band extension messages are normalized to absence, and
        metadata shared by all Bands is lifted onto the Asset. Locations,
        registries, and resulting Band profiles are validated for compilation.

        Args:
            assets: Assets to materialize, validate, and normalize. Keys must be
                nonempty and unique.

        Returns:
            A read-only, mapping-like collection keyed by each asset's key.

        Raises:
            TypeError: If an Asset, location, Band, or role has an invalid type.
            ValueError: If keys, locations, roles, media types, registries, or
                Band metadata cannot be represented by the ingestion format.
        """
        materialized = list(assets)
        result: dict[str, Asset] = {}
        for asset in materialized:
            if not isinstance(asset, Asset):
                raise TypeError(f"assets must contain Asset instances, got {type(asset).__name__}")
            _validate_authored_asset(asset)
            if asset.key in result:
                raise ValueError(f"duplicate asset key: {asset.key!r}")
            normalized = _normalize_asset(asset)
            for band in normalized.bands:
                if not _compile_band_profile(band, normalized).to_binary():
                    raise ValueError(f"asset {asset.key!r} has a band with no metadata after inheritance")
            result[asset.key] = normalized
        locations = [location for asset in result.values() for location in (asset.primary, *asset.alternates.values())]
        _merge_registry({}, locations, "storage_schemes")
        _merge_registry({}, locations, "authentication_schemes")
        return cls(MappingProxyType(result))

    @overload
    def to_fields(
        self,
        *,
        fields: None = None,
        storage: Storage | None = None,
        authentication: Authentication | None = None,
    ) -> AssetFields: ...

    @overload
    def to_fields(
        self,
        *,
        fields: AssetFieldNames,
        storage: Storage | None = None,
        authentication: Authentication | None = None,
    ) -> dict[str, Assets | Storage | Authentication]: ...

    def to_fields(
        self,
        *,
        fields: AssetFieldNames | None = None,
        storage: Storage | None = None,
        authentication: Authentication | None = None,
    ) -> AssetFields | dict[str, Assets | Storage | Authentication]:
        """Compile the semantic collection into optimized ingestion fields.

        Args:
            fields: Optional output names for assets, storage, and authentication.
            storage: Additional storage registry entries to retain, including
                entries referenced only by other STAC fields such as Links.
            authentication: Additional authentication registry entries to retain,
                including entries referenced only by other STAC fields such as Links.

        Returns:
            A field-name mapping containing ``Assets`` and nonempty registries.

        Raises:
            TypeError: If a configured field name is not a string.
            ValueError: If names collide, schemes conflict, or metadata is invalid.
        """
        overrides = _validate_field_names(fields)
        names = {**_ASSET_FIELD_DEFAULTS, **overrides}
        root, storage_schemes, auth_schemes = _compile_assets(self.values(), storage, authentication)
        result: dict[str, Assets | Storage | Authentication] = {names["assets"]: root}
        if storage_schemes:
            result[names["storage"]] = Storage(schemes=storage_schemes)
        if auth_schemes:
            result[names["authentication"]] = Authentication(schemes=auth_schemes)
        return cast("AssetFields", result) if fields is None else result

    def __getitem__(self, key: str) -> Asset:
        return self._assets[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._assets)

    def __len__(self) -> int:
        return len(self._assets)

    def __eq__(self, other: object) -> bool:
        """Compare collections by resolved asset semantics, not profile placement.

        Args:
            other: Object to compare with this collection.

        Returns:
            Whether both collections contain the same resolved asset metadata.
        """
        if not isinstance(other, AssetCollection):
            return NotImplemented
        return self.keys() == other.keys() and all(
            _semantic_equal(_asset_semantics(asset), _asset_semantics(other[key])) for key, asset in self.items()
        )


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


def _validate_field_names(fields: AssetFieldNames | None) -> dict[str, str]:
    """Validate runtime field-name overrides and return a plain snapshot."""
    if fields is None:
        return {}
    unknown = set(fields).difference(_ASSET_FIELD_DEFAULTS)
    if unknown:
        raise ValueError(f"unknown asset field names: {', '.join(sorted(unknown))}")
    overrides = dict(fields)
    for logical_name, physical_name in overrides.items():
        if not isinstance(physical_name, str):
            raise TypeError(f"field name for {logical_name!r} must be a string")
        if not physical_name:
            raise ValueError(f"field name for {logical_name!r} cannot be empty")
    resolved = {**_ASSET_FIELD_DEFAULTS, **overrides}
    if len(set(resolved.values())) != len(resolved):
        raise ValueError("asset, storage, and authentication field names must be distinct")
    return overrides


def _validate_authored_asset(asset: Asset) -> None:
    """Validate semantic invariants required by compilation and resolution."""
    if not asset.key:
        raise ValueError("asset key cannot be empty")
    _validate_authored_location(asset.primary, asset.key)
    for alternate_key, location in asset.alternates.items():
        if not alternate_key:
            raise ValueError(f"asset {asset.key!r} has an alternate with an empty key")
        _validate_authored_location(location, asset.key, alternate_key)
    if asset.media_type == "":
        raise ValueError(f"asset {asset.key!r} media type cannot be empty")
    if any(not isinstance(band, Band) for band in asset.bands):
        raise TypeError(f"asset {asset.key!r} bands must contain Band instances")
    _canonical_roles(asset.roles, asset.key)


def _validate_authored_location(location: object, asset_key: str, alternate_key: str | None = None) -> None:
    """Validate the type and href of one authored location."""
    label = "primary" if alternate_key is None else f"alternate {alternate_key!r}"
    if not isinstance(location, AssetLocation):
        raise TypeError(f"asset {asset_key!r} {label} must be an AssetLocation")
    if not location.href:
        raise ValueError(f"asset {asset_key!r} {label} location href cannot be empty")


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
        alternate_name=(
            source.alternate_name
            if source.has_field("alternate_name")
            else profile.default_alternate_name
            if profile.has_field("default_alternate_name")
            else None
        ),
        storage_schemes=_resolve_refs(storage, profile.storage_refs, "storage"),
        authentication_schemes=_resolve_refs(authentication, profile.auth_refs, "authentication"),
    )


def _merge_registry(
    base: Mapping[str, _MessageT], locations: Iterable[AssetLocation], attribute: _RegistryAttribute
) -> dict[str, _MessageT]:
    """Merge equal registry entries and reject conflicting uses of one key."""
    result = dict(base)
    for location in locations:
        for key, scheme in getattr(location, attribute).items():
            previous = result.get(key)
            if previous is not None and previous != scheme:
                raise ValueError(f"conflicting scheme for key {key!r}")
            if previous is None:
                result[key] = scheme
    return result


def _semantic_equal(left: Any, right: Any) -> bool:
    """Compare semantic values recursively, treating NaN values as equal."""
    if isinstance(left, Message) and isinstance(right, Message):
        return left == right
    if isinstance(left, float) and isinstance(right, float) and isnan(left) and isnan(right):
        return True
    if isinstance(left, Mapping) and isinstance(right, Mapping):
        return left.keys() == right.keys() and all(_semantic_equal(value, right[key]) for key, value in left.items())
    if isinstance(left, (tuple, list)) and isinstance(right, (tuple, list)):
        return len(left) == len(right) and all(_semantic_equal(a, b) for a, b in zip(left, right, strict=True))
    if is_dataclass(left) and is_dataclass(right) and type(left) is type(right):
        return all(
            _semantic_equal(getattr(left, field.name), getattr(right, field.name)) for field in dataclass_fields(left)
        )
    return left == right


def _common(values: Iterable[Any]) -> Any:
    materialized = list(values)
    if not materialized:
        return _NO_COMMON
    return materialized[0] if all(_semantic_equal(materialized[0], value) for value in materialized[1:]) else _NO_COMMON


def _message_value(message: Message[Any] | None, field: str, unspecified: Any = None) -> Any:
    if message is None:
        return unspecified
    value = getattr(message, field)
    if isinstance(value, list):
        return tuple(value)
    if unspecified is not None and value == unspecified:
        return unspecified
    return value if message.has_field(field) else unspecified


def _safe_common_href_prefix(hrefs: Iterable[str]) -> str:
    """Return a byte-preserving common href prefix ending at a path boundary."""
    values = list(hrefs)
    prefix = values[0]
    for value in values[1:]:
        mismatch = next(
            (index for index, pair in enumerate(zip(prefix, value, strict=False)) if pair[0] != pair[1]),
            min(len(prefix), len(value)),
        )
        prefix = prefix[:mismatch]
    boundary = prefix.rfind("/")
    return prefix[: boundary + 1] if boundary >= 0 else ""


def _encode_media_type(value: MediaType | str | None) -> ProtoMediaType | None:
    """Encode an exact media-type string using the compact known dictionary."""
    if value is None:
        return None
    for known, text in _MEDIA_TYPES.items():
        if value == text:
            return ProtoMediaType(known=known)
    return ProtoMediaType(custom=value)


def _canonical_roles(roles: Iterable[KnownAssetRole | str], asset_key: str) -> frozenset[KnownAssetRole | str]:
    """Canonicalize known role strings and validate all authored role values."""
    canonical: set[KnownAssetRole | str] = set()
    for role in roles:
        if isinstance(role, KnownAssetRole):
            if role == KnownAssetRole.UNSPECIFIED:
                raise ValueError(f"asset {asset_key!r} has an invalid role")
            canonical.add(role)
        elif isinstance(role, str):
            if not role:
                raise ValueError(f"asset {asset_key!r} has an invalid role")
            canonical.add(_KNOWN_ROLES.get(role, role))
        else:
            raise TypeError(f"asset {asset_key!r} has a role of unsupported type {type(role).__name__}")
    return frozenset(canonical)


def _compile_assets(
    authored: Iterable[Asset],
    storage: Storage | None,
    authentication: Authentication | None,
) -> tuple[Assets, dict[str, StorageScheme], dict[str, AuthenticationScheme]]:
    """Compile semantic assets into compact generated ingestion messages.

    Compilation lifts shared effective Band metadata onto each Asset, removes
    inherited values from Band profiles, interns and deterministically orders
    equal Band and access profiles, compresses hrefs at URI path boundaries,
    and merges referenced storage and authentication registries.

    Args:
        authored: Semantic assets to compile.
        storage: Additional storage entries, including entries used by Links.
        authentication: Additional authentication entries, including entries
            used by Links.

    Returns:
        The optimized Assets message and merged storage and authentication
        registries.
    """
    assets = sorted((_normalize_asset(asset) for asset in authored), key=lambda asset: asset.key)
    locations = [location for asset in assets for location in (asset.primary, *asset.alternates.values())]
    storage_schemes = _merge_registry(storage.schemes if storage is not None else {}, locations, "storage_schemes")
    auth_schemes = _merge_registry(
        authentication.schemes if authentication is not None else {}, locations, "authentication_schemes"
    )
    access_profiles, location_specs, indices = _compile_access_profiles(assets)
    unsorted_band_profiles: dict[bytes, ProtoBand] = {}
    asset_band_keys: dict[str, list[bytes]] = {}
    proto_assets: list[ProtoAsset] = []
    for asset in assets:
        band_keys = []
        for band in asset.bands:
            profile = _compile_band_profile(band, asset)
            key = profile.to_binary()
            if not key:
                raise ValueError(f"asset {asset.key!r} has a band with no metadata after inheritance")
            unsorted_band_profiles.setdefault(key, profile)
            band_keys.append(key)
        asset_band_keys[asset.key] = band_keys
        roles = _canonical_roles(asset.roles, asset.key)
        known_roles = {role for role in roles if isinstance(role, KnownAssetRole)}
        known_roles_list = sorted(known_roles, key=lambda role: role.value)
        custom_roles = sorted(role for role in roles if isinstance(role, str))
        primary_spec = location_specs[(asset.key, "")]
        primary_suffix = asset.primary.href.removeprefix(primary_spec.base_href)
        primary = ProtoAssetLocation(
            access_profile_index=indices[primary_spec],
            href=primary_suffix,
            alternate_name=None
            if asset.primary.alternate_name == primary_spec.default_alternate_name
            else asset.primary.alternate_name,
        )
        alternates = []
        for key, location in sorted(asset.alternates.items()):
            spec = location_specs[(asset.key, key)]
            suffix = location.href.removeprefix(spec.base_href)
            alternates.append(
                ProtoAssetLocation(
                    access_profile_index=indices[spec],
                    href=None if suffix == primary_suffix else suffix,
                    alternate_name=None
                    if location.alternate_name == spec.default_alternate_name
                    else location.alternate_name,
                )
            )
        proto_assets.append(
            ProtoAsset(
                key=asset.key,
                primary=primary,
                alternates=alternates,
                media_type=_encode_media_type(asset.media_type),
                title=asset.title,
                description=asset.description,
                roles=known_roles_list,
                custom_roles=custom_roles,
                gsd=asset.gsd,
                data_type=asset.data_type,
                nodata=asset.nodata,
                statistics=asset.statistics,
                unit=asset.unit,
                eo=asset.eo,
                raster=asset.raster,
                projection=asset.projection,
                view=asset.view,
                classes=list(asset.classes),
                file=asset.file,
                sar=asset.sar,
                satellite=asset.satellite,
                product=asset.product,
            )
        )
    band_profiles = sorted(unsorted_band_profiles.values(), key=_band_profile_sort_key)
    band_indices = {profile.to_binary(): index for index, profile in enumerate(band_profiles)}
    for proto_asset in proto_assets:
        proto_asset.band_profile_indices.extend(band_indices[key] for key in asset_band_keys[proto_asset.key])
    return (
        Assets(access_profiles=access_profiles, band_profiles=band_profiles, assets=proto_assets),
        storage_schemes,
        auth_schemes,
    )


def _compile_access_profiles(
    assets: list[Asset],
) -> tuple[
    list[AssetAccessProfile],
    dict[tuple[str, str], _AccessProfileSpec],
    dict[_AccessProfileSpec, int],
]:
    """Build deterministic, href-compressing profiles for asset locations."""
    groups: dict[
        tuple[str, tuple[str, ...], tuple[str, ...]],
        list[tuple[str, AssetLocation]],
    ] = {}
    for asset in assets:
        if "" in asset.alternates:
            raise ValueError(f"asset {asset.key!r} has an alternate with an empty key")
        ordered = [("", asset.primary), *sorted(asset.alternates.items())]
        for alternate_key, location in ordered:
            if not location.href:
                raise ValueError(f"asset {asset.key!r} location href cannot be empty")
            group = (
                alternate_key,
                tuple(sorted(location.storage_schemes)),
                tuple(sorted(location.authentication_schemes)),
            )
            groups.setdefault(group, []).append((asset.key, location))
    profile_specs = []
    location_specs: dict[tuple[str, str], _AccessProfileSpec] = {}
    for (alternate_key, storage_refs, auth_refs), grouped_locations in groups.items():
        base_href = _safe_common_href_prefix(location.href for _, location in grouped_locations)
        alternate_names = [location.alternate_name for _, location in grouped_locations]
        default_name = (
            alternate_names[0]
            if alternate_names and alternate_names[0] is not None and len(set(alternate_names)) == 1
            else None
        )
        spec = _AccessProfileSpec(alternate_key, default_name, base_href, storage_refs, auth_refs)
        profile_specs.append(spec)
        for asset_key, _ in grouped_locations:
            location_specs[(asset_key, alternate_key)] = spec
    sorted_specs = sorted(
        profile_specs,
        key=lambda item: (
            bool(item.alternate_key),
            item.alternate_key,
            item.storage_refs,
            item.authentication_refs,
            item.base_href,
            item.default_alternate_name is not None,
            item.default_alternate_name or "",
        ),
    )
    indices = {spec: index for index, spec in enumerate(sorted_specs)}
    access_profiles = [
        AssetAccessProfile(
            alternate_key=spec.alternate_key,
            default_alternate_name=spec.default_alternate_name,
            base_href=spec.base_href,
            storage_refs=list(spec.storage_refs),
            auth_refs=list(spec.authentication_refs),
        )
        for spec in sorted_specs
    ]
    return access_profiles, location_specs, indices


def _compile_band_profile(band: Band, asset: Asset) -> ProtoBand:
    """Compile one effective Band into its sparse, inheriting profile."""
    return ProtoBand(
        name=band.name,
        description=band.description,
        data_type=None if band.data_type == asset.data_type else band.data_type,
        nodata=None if _semantic_equal(band.nodata, asset.nodata) else band.nodata,
        unit=None if band.unit == asset.unit else band.unit,
        eo=_sparse_eo(band.eo, asset.eo),
        raster=_sparse_raster(band.raster, asset.raster),
        classes=[] if _semantic_equal(band.classes, asset.classes) else list(band.classes),
        sar=_sparse_sar(band.sar, asset.sar),
    )


def _effective_band(band: Band, asset: Asset) -> Band:
    """Resolve one Band by applying all inheritable Asset defaults."""
    return Band(
        name=band.name,
        description=band.description,
        data_type=band.data_type if band.data_type != DataType.UNSPECIFIED else asset.data_type,
        nodata=band.nodata if band.nodata is not None else asset.nodata,
        unit=band.unit if band.unit is not None else asset.unit,
        eo=_inherit_eo(band.eo, asset.eo),
        raster=_inherit_raster(band.raster, asset.raster),
        classes=band.classes or asset.classes,
        sar=_inherit_sar(band.sar, asset.sar),
    )


def _normalize_asset(asset: Asset) -> Asset:
    """Return the canonical semantic form produced again by resolution.

    Band values are first resolved against authored Asset defaults. Values that
    are effectively common to every Band are then lifted onto the Asset using
    the same rules as protobuf compilation. EO identity deliberately remains
    Band-scoped unless it was already authored on the Asset.
    """
    roles = _canonical_roles(asset.roles, asset.key)
    if not asset.bands:
        return replace(asset, roles=roles)
    bands = tuple(_normalize_band_extensions(_effective_band(band, asset)) for band in asset.bands)
    common_data_type = _common(band.data_type for band in bands)
    common_nodata = _common(band.nodata for band in bands)
    common_unit = _common(band.unit for band in bands)
    common_classes = _common(band.classes for band in bands)
    return replace(
        asset,
        roles=roles,
        bands=bands,
        data_type=asset.data_type if common_data_type is _NO_COMMON else common_data_type,
        nodata=asset.nodata if common_nodata is _NO_COMMON else common_nodata,
        unit=asset.unit if common_unit is _NO_COMMON else common_unit,
        raster=_lift_raster(bands, asset.raster),
        classes=asset.classes if common_classes is _NO_COMMON else common_classes,
        sar=_lift_sar(bands, asset.sar),
    )


def _asset_semantics(asset: Asset) -> Asset:
    """Normalize an Asset for profile-placement-independent equality."""
    return _normalize_asset(asset)


def _normalize_band_extensions(band: Band) -> Band:
    """Canonicalize present but empty generated Band metadata to absence."""
    return replace(
        band,
        eo=band.eo if band.eo is not None and band.eo.to_binary() else None,
        raster=band.raster if band.raster is not None and band.raster.to_binary() else None,
        sar=band.sar if band.sar is not None and band.sar.to_binary() else None,
    )


def _lift_raster(bands: tuple[Band, ...], parent: RasterProperties | None) -> RasterProperties | None:
    """Lift Raster fields effectively shared by every Band onto the Asset.

    This is the parent-building half of compilation. ``_sparse_raster`` then
    removes those inherited values from each child profile; ``_inherit_raster``
    performs the inverse reconstruction while resolving queried data.
    """
    if not bands:
        return parent
    common_sampling = _common(_message_value(band.raster, "sampling", RasterSampling.UNSPECIFIED) for band in bands)
    sampling = (
        _message_value(parent, "sampling", RasterSampling.UNSPECIFIED)
        if common_sampling is _NO_COMMON
        else common_sampling
    )
    values = {}
    for field in ("scale", "offset", "spatial_resolution"):
        common = _common(_message_value(band.raster, field) for band in bands)
        values[field] = _message_value(parent, field) if common is _NO_COMMON else common
    result = RasterProperties(sampling=sampling, **values)
    return result if result.to_binary() else None


def _lift_sar(bands: tuple[Band, ...], parent: SARProperties | None) -> SARProperties | None:
    """Lift SAR fields effectively shared by every Band onto the Asset.

    This complements ``_sparse_sar`` during compilation. ``_inherit_sar`` is
    the inverse operation used when resolving Band profiles.
    """
    if not bands:
        return parent
    values = {}
    for field in _SAR_FIELDS:
        default = _SAR_ENUM_DEFAULTS.get(field)
        common = _common(_message_value(band.sar, field, default) for band in bands)
        values[field] = _message_value(parent, field, default) if common is _NO_COMMON else common
    values["polarizations"] = list(values["polarizations"] or ())
    values["beam_ids"] = list(values["beam_ids"] or ())
    result = SARProperties(**values)
    return result if result.to_binary() else None


def _sparse_eo(child: EOProperties | None, parent: EOProperties | None) -> EOProperties | None:
    """Remove EO fields inherited from an already-authored Asset EO value."""
    if child is None:
        return None
    result = EOProperties(
        common_name=None if parent is not None and child.common_name == parent.common_name else child.common_name,
        center_wavelength=None
        if _semantic_equal(_message_value(child, "center_wavelength"), _message_value(parent, "center_wavelength"))
        else _message_value(child, "center_wavelength"),
        full_width_half_max=None
        if _semantic_equal(_message_value(child, "full_width_half_max"), _message_value(parent, "full_width_half_max"))
        else _message_value(child, "full_width_half_max"),
        solar_illumination=None
        if _semantic_equal(_message_value(child, "solar_illumination"), _message_value(parent, "solar_illumination"))
        else _message_value(child, "solar_illumination"),
    )
    return result if result.to_binary() else None


def _sparse_raster(child: RasterProperties | None, parent: RasterProperties | None) -> RasterProperties | None:
    """Remove Raster fields inherited from the canonical Asset value.

    This complements ``_lift_raster`` during compilation; ``_inherit_raster``
    reconstructs the effective value during resolution.
    """
    if child is None:
        return None
    result = RasterProperties(
        sampling=None if parent is not None and child.sampling == parent.sampling else child.sampling,
        scale=None
        if _semantic_equal(_message_value(child, "scale"), _message_value(parent, "scale"))
        else _message_value(child, "scale"),
        offset=None
        if _semantic_equal(_message_value(child, "offset"), _message_value(parent, "offset"))
        else _message_value(child, "offset"),
        spatial_resolution=None
        if _semantic_equal(_message_value(child, "spatial_resolution"), _message_value(parent, "spatial_resolution"))
        else _message_value(child, "spatial_resolution"),
    )
    return result if result.to_binary() else None


def _sparse_sar(child: SARProperties | None, parent: SARProperties | None) -> SARProperties | None:
    """Remove SAR fields inherited from the canonical Asset value.

    This complements ``_lift_sar`` during compilation; ``_inherit_sar``
    reconstructs the effective value during resolution.
    """
    if child is None:
        return None
    values = {}
    for field in _SAR_FIELDS:
        default = _SAR_ENUM_DEFAULTS.get(field)
        value = _message_value(child, field, default)
        values[field] = None if _semantic_equal(value, _message_value(parent, field, default)) else value
    values["polarizations"] = list(values["polarizations"] or ())
    values["beam_ids"] = list(values["beam_ids"] or ())
    result = SARProperties(**values)
    return result if result.to_binary() else None


def _band_profile_sort_key(profile: ProtoBand) -> tuple[Any, ...]:
    """Return the canonical ordering key for an interned Band profile."""
    center = _message_value(profile.eo, "center_wavelength")
    return (
        0 if center is not None else 1,
        center if center is not None else 0,
        0 if profile.has_field("name") else 1,
        profile.name if profile.has_field("name") else "",
        profile.to_binary(),
    )


def _inherit_eo(child: EOProperties | None, parent: EOProperties | None) -> EOProperties | None:
    """Resolve effective EO fields from a sparse child and its Asset parent."""
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


def _media_type(source: ProtoMediaType | None) -> MediaType | str | None:
    if source is None:
        return None
    has_known = source.has_field("known")
    has_custom = source.has_field("custom")
    if has_known == has_custom:
        raise ValueError("asset media type must contain exactly one known or custom value")
    if has_custom:
        if not source.custom:
            raise ValueError("asset custom media type cannot be empty")
        return source.custom
    if source.known not in _MEDIA_TYPES:
        raise ValueError(f"asset has invalid known media type {source.known!r}")
    return _MEDIA_TYPES[source.known]


def _inherit_raster(child: RasterProperties | None, parent: RasterProperties | None) -> RasterProperties | None:
    """Reconstruct effective Raster fields from sparse child and parent values."""
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
    """Reconstruct effective SAR fields from sparse child and parent values."""
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


def _resolve_primary_location(
    source: ProtoAsset,
    profiles: list[AssetAccessProfile],
    storage: Mapping[str, StorageScheme],
    authentication: Mapping[str, AuthenticationScheme],
) -> tuple[AssetLocation, str | None]:
    if source.primary is None:
        raise ValueError(f"asset {source.key!r} has no primary location")
    primary_suffix = source.primary.href if source.primary.has_field("href") else None
    primary_key, primary = _location(source.primary, profiles, storage, authentication)
    if primary_key:
        raise ValueError(f"asset {source.key!r} primary location uses alternate profile {primary_key!r}")
    if not primary.href:
        raise ValueError(f"asset {source.key!r} primary location href cannot be empty")
    return primary, primary_suffix


def _resolve_assets(
    root: Assets,
    storage_message: Storage | None,
    authentication_message: Authentication | None,
) -> Mapping[str, Asset]:
    storage = storage_message.schemes if storage_message is not None else {}
    authentication = authentication_message.schemes if authentication_message is not None else {}
    result: dict[str, Asset] = {}
    for source in root.assets:
        if not source.key:
            raise ValueError("asset key cannot be empty")
        primary, primary_suffix = _resolve_primary_location(source, root.access_profiles, storage, authentication)
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
            if not alternate.href:
                raise ValueError(f"asset {source.key!r} alternate {alternate_key!r} href cannot be empty")
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
            roles=_canonical_roles([*source.roles, *source.custom_roles], source.key),
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
