"""Asset-oriented asynchronous storage access."""

import os
import sys
import threading
import uuid
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass
from os import PathLike
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import unquote, urlsplit

if TYPE_CHECKING:
    from async_geotiff import GeoTIFF
    from obstore.store import ObjectStore

    from tilebox.datasets.assets.assets import Asset, AssetLocation
    from tilebox.datasets.datasets.stac.v1.authentication_pb import AuthenticationScheme
    from tilebox.datasets.datasets.stac.v1.storage_pb import StorageScheme


@dataclass(frozen=True, slots=True)
class AssetAccessPolicy:
    """Policy controlling deterministic asset-location selection."""

    preferred_schemes: tuple[str, ...] = ("file", "s3", "gs", "az", "https", "http")


@dataclass(frozen=True, slots=True)
class ResolvedAsset:
    """A resolved asset location ready for object-level access."""

    asset: "Asset"
    location: "AssetLocation"
    href: str
    store: "ObjectStore"
    path: str
    storage_scheme: "StorageScheme | None"
    authentication_scheme: "AuthenticationScheme | None"


class Client:
    """Resolve and access dataset assets using reusable object stores."""

    def __init__(self, *, policy: AssetAccessPolicy | None = None) -> None:
        """Create an asset storage client.

        Args:
            policy: Location-selection policy. By default local, S3, Google Cloud,
                Azure, and HTTP locations are preferred in that order.
        """
        self.policy = policy or AssetAccessPolicy()
        self._stores: dict[tuple[Any, ...], ObjectStore] = {}
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
                storage = _select_scheme(location.storage_schemes, "storage")
                authentication = _select_scheme(location.authentication_schemes, "authentication")
                store, path = self._store_for(location.href, storage, authentication)
            except (TypeError, ValueError) as error:
                rejected.append(f"{label} ({location.href!r}): {error}")
                continue
            return ResolvedAsset(asset, location, location.href, store, path, storage, authentication)
        details = "; ".join(rejected) or "asset has no locations"
        raise ValueError(f"unable to resolve asset {asset.key!r}: {details}")

    def _store_for(  # noqa: C901, PLR0912, PLR0915
        self,
        href: str,
        storage: "StorageScheme | None",
        authentication: "AuthenticationScheme | None",
    ) -> "tuple[ObjectStore, str]":
        from obstore.store import AzureStore, GCSStore, HTTPStore, LocalStore, S3Store  # noqa: PLC0415

        parsed = urlsplit(href)
        scheme = _uri_scheme(href)
        authentication_type = _authentication_type(authentication)
        if authentication is not None and authentication_type != "s3":
            raise ValueError(f"authentication type {authentication_type!r} is unsupported")

        if scheme == "file":
            identity = ("file", "/")
            constructor = lambda: LocalStore("/")  # noqa: E731
            path = unquote(parsed.path if parsed.scheme else href).lstrip("/")
        elif scheme == "s3":
            storage_type = _storage_type(storage)
            if storage is not None and storage_type not in {"aws_s3", "custom_s3", "unspecified"}:
                raise ValueError(f"storage type {storage_type!r} is incompatible with s3")
            authenticated = authentication is not None
            options = (
                storage.region if storage and storage.has_field("region") else None,
                storage.requester_pays if storage and storage.has_field("requester_pays") else None,
                not authenticated,
                storage.platform if storage and storage_type == "custom_s3" and storage.platform else None,
            )
            identity = ("s3", parsed.netloc, *options, repr(authentication))
            constructor = lambda: S3Store(  # noqa: E731
                parsed.netloc,
                **{
                    key: value
                    for key, value in {
                        "region": options[0],
                        "request_payer": options[1],
                        "skip_signature": options[2],
                        "endpoint": options[3],
                    }.items()
                    if value is not None
                },
            )
            path = parsed.path.lstrip("/")
        elif scheme in {"gs", "gcs"}:
            storage_type = _storage_type(storage)
            if storage is not None and storage_type not in {"google_cloud_storage", "unspecified"}:
                raise ValueError(f"storage type {storage_type!r} is incompatible with Google Cloud Storage")
            anonymous = authentication is None
            identity = ("gs", parsed.netloc, anonymous, repr(authentication))
            constructor = lambda: GCSStore(parsed.netloc, skip_signature=anonymous)  # noqa: E731
            path = parsed.path.lstrip("/")
        elif scheme in {"az", "azure"}:
            segments = parsed.path.lstrip("/").split("/", 1)
            if not parsed.netloc or not segments[0]:
                raise ValueError("Azure href must have the form az://account/container/path")
            container = segments[0]
            path = segments[1] if len(segments) == 2 else ""
            identity = ("az", parsed.netloc, container, repr(authentication))
            constructor = lambda: AzureStore(container, account_name=parsed.netloc)  # noqa: E731
        elif scheme in {"http", "https"}:
            if authentication is not None:
                raise ValueError("authenticated HTTP locations are not supported yet")
            origin = f"{scheme}://{parsed.netloc}"
            identity = (scheme, origin)
            constructor = lambda: HTTPStore(origin)  # noqa: E731
            path = parsed.path.lstrip("/")
            if parsed.query:
                path = f"{path}?{parsed.query}"
        else:
            raise ValueError(f"unsupported URI scheme {scheme!r}")

        with self._stores_lock:
            store = self._stores.get(identity)
            if store is None:
                store = constructor()
                self._stores[identity] = store
        return store, path

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
        try:
            from async_geotiff import GeoTIFF  # noqa: PLC0415
        except ImportError:
            if sys.version_info < (3, 11):
                raise ImportError(
                    "open_geotiff is unavailable on Python 3.10 because async-geotiff requires Python 3.11 or newer"
                ) from None
            raise ImportError("async-geotiff is required by tilebox-storage but could not be imported") from None
        resolved = self.resolve(asset)
        return await GeoTIFF.open(
            resolved.path,
            store=resolved.store,
            prefetch=prefetch,
            multiplier=multiplier,
        )


def _uri_scheme(href: str) -> str:
    return urlsplit(href).scheme.lower() or "file"


def _storage_type(storage: "StorageScheme | None") -> str | None:
    if storage is None:
        return None
    if storage.has_field("custom_type"):
        return storage.custom_type
    from tilebox.datasets.datasets.stac.v1.storage_pb import KnownStorageType  # noqa: PLC0415

    return {
        KnownStorageType.UNSPECIFIED: "unspecified",
        KnownStorageType.AWS_S3: "aws_s3",
        KnownStorageType.CUSTOM_S3: "custom_s3",
        KnownStorageType.MICROSOFT_AZURE: "microsoft_azure",
        KnownStorageType.GOOGLE_CLOUD_STORAGE: "google_cloud_storage",
    }[storage.known_type]


def _authentication_type(authentication: "AuthenticationScheme | None") -> str | None:
    if authentication is None:
        return None
    if authentication.has_field("custom_type"):
        return authentication.custom_type
    from tilebox.datasets.datasets.stac.v1.authentication_pb import KnownAuthenticationType  # noqa: PLC0415

    return {
        KnownAuthenticationType.UNSPECIFIED: "unspecified",
        KnownAuthenticationType.HTTP: "http",
        KnownAuthenticationType.S3: "s3",
        KnownAuthenticationType.SIGNED_URL: "signed_url",
        KnownAuthenticationType.OAUTH2: "oauth2",
        KnownAuthenticationType.API_KEY: "api_key",
        KnownAuthenticationType.OPEN_ID_CONNECT: "open_id_connect",
    }[authentication.known_type]


def _select_scheme(schemes: Mapping[str, Any], kind: str) -> Any | None:
    if len(schemes) > 1:
        keys = ", ".join(repr(key) for key in schemes)
        raise ValueError(f"multiple {kind} schemes are applicable ({keys})")
    return next(iter(schemes.values()), None)


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
