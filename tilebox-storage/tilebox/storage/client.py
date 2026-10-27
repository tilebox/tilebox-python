"""Asset-oriented asynchronous storage access."""

import os
import threading
import uuid
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass
from os import PathLike
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

from tilebox.storage._registry import Registry, StoreSpec

if TYPE_CHECKING:
    from async_geotiff import GeoTIFF
    from obstore.store import ObjectStore, S3CredentialProvider

    from tilebox.datasets.assets.assets import Asset, AssetLocation
    from tilebox.datasets.stac.v1.authentication_pb import AuthenticationScheme
    from tilebox.datasets.stac.v1.storage_pb import StorageScheme


@dataclass(frozen=True, slots=True)
class AssetAccessPolicy:
    """Policy controlling deterministic asset-location selection."""

    preferred_schemes: tuple[str, ...] = ("file", "s3", "gs", "gcs", "az", "azure", "abfs", "abfss", "https", "http")


@dataclass(frozen=True, slots=True)
class ResolvedAsset:
    """A resolved asset location ready for object-level access."""

    asset: "Asset"
    location: "AssetLocation"
    store: "ObjectStore"
    path: str
    storage_scheme: "StorageScheme | None"
    authentication_scheme: "AuthenticationScheme | None"

    @property
    def href(self) -> str:
        """The original selected location, never a refreshed signed URL."""
        return self.location.href


class Client:
    """Resolve and access dataset assets using reusable object stores."""

    def __init__(
        self,
        *,
        policy: AssetAccessPolicy | None = None,
        s3_credentials: Mapping[str, "S3CredentialProvider"] | None = None,
    ) -> None:
        """Create an asset storage client.

        Args:
            policy: Location-selection policy. By default local, S3, Google Cloud,
                Azure, and HTTP locations are preferred in that order.
            s3_credentials: Explicit S3 credential providers keyed by the location's
                authentication scheme name. The mapping is copied at construction;
                providers are invoked on reads, not during resolution. Locations
                without authentication metadata always use unsigned cloud requests.
        """
        self.policy = policy or AssetAccessPolicy()
        self._registry = Registry.default(s3_credentials=s3_credentials)
        self._stores: dict[StoreSpec, ObjectStore] = {}
        self._stores_lock = threading.RLock()

    def resolve(self, asset: "Asset") -> ResolvedAsset:
        """Resolve an asset without making a network request.

        Args:
            asset: Asset whose best supported location should be selected.

        Returns:
            The selected location, object store, object path, and access metadata.

        Raises:
            ValueError: If no location can be accessed by this client.
        """
        candidates = [("primary", asset.primary), *asset.alternates.items()]
        rank = {scheme: index for index, scheme in enumerate(self.policy.preferred_schemes)}
        candidates.sort(key=lambda item: rank.get(_uri_scheme(item[1].href), len(rank)))

        rejected = []
        for label, location in candidates:
            try:
                spec, path, storage, authentication = self._registry.resolve(location)
                store = self._store_for(spec)
            except (TypeError, ValueError) as error:
                rejected.append(f"{label}: {error}")
                continue
            return ResolvedAsset(asset, location, store, path, storage, authentication)
        details = "; ".join(rejected) or "asset has no locations"
        raise ValueError(f"unable to resolve asset {asset.key!r}: {details}")

    def _store_for(self, spec: StoreSpec) -> "ObjectStore":
        with self._stores_lock:
            store = self._stores.get(spec)
            if store is None:
                store = self._registry.create_store(spec)
                self._stores[spec] = store
        return store

    async def read_bytes(
        self,
        asset: "Asset",
        *,
        max_bytes: int | None = None,
    ) -> bytes:
        """Read an entire asset into memory.

        Args:
            asset: Asset to resolve and read.
            max_bytes: Optional maximum accepted object size. The request is rejected
                before reading when the provider reports a larger size, and checked
                again after reading when no reliable size was available beforehand.

        Returns:
            The complete object contents as Python bytes.
        """
        import obstore  # noqa: PLC0415

        resolved = self.resolve(asset)
        result = await obstore.get_async(resolved.store, resolved.path)
        size = result.meta.get("size")
        if max_bytes is not None and size is not None and size > max_bytes:
            raise ValueError(f"asset size {size} exceeds max_bytes={max_bytes}")
        data = bytes(await result.bytes_async())
        if max_bytes is not None and len(data) > max_bytes:
            raise ValueError(f"asset size {len(data)} exceeds max_bytes={max_bytes}")
        return data

    async def iter_bytes(
        self,
        asset: "Asset",
    ) -> AsyncIterator[bytes]:
        """Stream an asset as provider-dependent byte chunks.

        Args:
            asset: Asset to resolve and stream.

        Yields:
            Byte chunks whose sizes are chosen by the storage provider.
        """
        import obstore  # noqa: PLC0415

        resolved = self.resolve(asset)
        result = await obstore.get_async(resolved.store, resolved.path)
        async for chunk in result:
            yield bytes(chunk)

    async def download(
        self,
        asset: "Asset",
        destination: str | PathLike[str],
        *,
        overwrite: bool = False,
    ) -> Path:
        """Atomically download an asset to an exact local file path.

        Args:
            asset: Asset to resolve and download.
            destination: Exact destination file path. Parent directories are created.
            overwrite: Replace an existing destination when true; otherwise raise
                :class:`FileExistsError`.

        Returns:
            The destination path.
        """
        destination = Path(destination)
        if destination.exists() and not overwrite:
            raise FileExistsError(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
        try:
            with temporary.open("xb") as output:
                async for chunk in self.iter_bytes(asset):
                    output.write(chunk)
            if overwrite:
                temporary.replace(destination)
            else:
                os.link(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)
        return destination

    async def open_geotiff(
        self,
        asset: "Asset",
        *,
        prefetch: int = 32768,
        multiplier: float = 2.0,
    ) -> "GeoTIFF":
        """Open a GeoTIFF without reading pixel data.

        Args:
            asset: GeoTIFF asset to resolve and open.
            prefetch: Number of bytes initially fetched to parse TIFF metadata.
            multiplier: Growth factor for subsequent metadata range requests.

        Returns:
            An async-geotiff ``GeoTIFF`` using the resolved object store.
        """
        media_type = (asset.media_type or "").lower()
        if media_type and not media_type.startswith(("image/tiff", "image/geotiff", "application/geotiff")):
            raise ValueError(f"asset media type {asset.media_type!r} is not compatible with GeoTIFF")
        from async_geotiff import GeoTIFF  # noqa: PLC0415

        resolved = self.resolve(asset)
        return await GeoTIFF.open(
            resolved.path,
            store=resolved.store,
            prefetch=prefetch,
            multiplier=multiplier,
        )


def _uri_scheme(href: str) -> str:
    return urlsplit(href).scheme.lower() or "file"


_default_client = Client()


async def read_bytes(
    asset: "Asset",
    *,
    max_bytes: int | None = None,
) -> bytes:
    """Read an entire asset using the shared default client."""
    return await _default_client.read_bytes(asset, max_bytes=max_bytes)


def iter_bytes(asset: "Asset") -> AsyncIterator[bytes]:
    """Stream an asset using the shared default client."""
    return _default_client.iter_bytes(asset)


async def download(
    asset: "Asset",
    destination: str | PathLike[str],
    *,
    overwrite: bool = False,
) -> Path:
    """Download an asset using the shared default client."""
    return await _default_client.download(asset, destination, overwrite=overwrite)


async def open_geotiff(
    asset: "Asset",
    *,
    prefetch: int = 32768,
    multiplier: float = 2.0,
) -> "GeoTIFF":
    """Open a GeoTIFF using the shared default client."""
    return await _default_client.open_geotiff(asset, prefetch=prefetch, multiplier=multiplier)
