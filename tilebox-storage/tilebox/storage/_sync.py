from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar, cast

from tilebox.storage.aio import ASFStorageClient as _ASFStorageClient
from tilebox.storage.aio import CopernicusStorageClient as _CopernicusStorageClient
from tilebox.storage.aio import LocalFileSystemStorageClient as _LocalFileSystemStorageClient
from tilebox.storage.aio import UmbraStorageClient as _UmbraStorageClient
from tilebox.storage.aio import USGSLandsatStorageClient as _USGSLandsatStorageClient

if TYPE_CHECKING:
    import xarray as xr

    from tilebox.storage.granule import (
        ASFStorageGranule,
        CopernicusStorageGranule,
        LocationStorageGranule,
        UmbraStorageGranule,
        USGSLandsatStorageGranule,
    )

# These classes live here to keep the package import light, but remain public tilebox.storage classes. Keeping their
# module identity stable preserves repr, introspection, and pickle lookup compatibility.

_T = TypeVar("_T")


def _run(coroutine: Coroutine[Any, Any, _T]) -> _T:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coroutine)

    # A synchronous caller blocks its own loop. Use a separate thread, preserving tracing and logging context.
    with ThreadPoolExecutor(max_workers=1) as executor:
        return cast(_T, executor.submit(copy_context().run, asyncio.run, coroutine).result())


class ASFStorageClient:
    __module__ = "tilebox.storage"

    def __init__(self, user: str, password: str, cache_directory: Path = Path.home() / ".cache" / "tilebox") -> None:
        """A tilebox storage client that downloads data from the Alaska Satellite Facility.

        Args:
            user: The username to use for authentication.
            password: The password to use for authentication.
            cache_directory: The directory to store downloaded data in. Defaults to ~/.cache/tilebox. If set to None
               no cache is used and the `output_dir` parameter will need be set when downloading data.
        """
        self._client = _ASFStorageClient(user, password, cache_directory)

    def download(
        self,
        datapoint: xr.Dataset | ASFStorageGranule,
        output_dir: Path | None = None,
        verify: bool = True,
        extract: bool = True,
        show_progress: bool = True,
    ) -> Path:
        """Download the data for a datapoint, and optionally verify and extract it."""
        return _run(self._client.download(datapoint, output_dir, verify, extract, show_progress))

    def download_quicklook(self, datapoint: xr.Dataset | ASFStorageGranule) -> Path:
        """Download the quicklook image for a datapoint."""
        return _run(self._client.download_quicklook(datapoint))

    def quicklook(self, datapoint: xr.Dataset | ASFStorageGranule, width: int = 600, height: int = 600) -> None:
        """Display the quicklook image in IPython."""
        _run(self._client.quicklook(datapoint, width, height))

    def delete(self, file_or_directory: Path) -> None:
        """Delete a product from the download cache."""
        _run(self._client.delete(file_or_directory))

    def destroy_cache(self) -> None:
        """Clear the download cache, deleting all entries."""
        _run(self._client.destroy_cache())


class UmbraStorageClient:
    __module__ = "tilebox.storage"

    def __init__(self, cache_directory: Path | None = Path.home() / ".cache" / "tilebox") -> None:
        """A tilebox storage client that downloads data from the Umbra Open Data Catalog.

        Args:
            cache_directory: The directory to store downloaded data in. Defaults to ~/.cache/tilebox. If set to None
               no cache is used and the `output_dir` parameter will need be set when downloading data.
        """
        self._client = _UmbraStorageClient(cache_directory)

    def list_objects(self, datapoint: xr.Dataset | UmbraStorageGranule) -> list[str]:
        """List object keys relative to the granule location."""
        return _run(self._client.list_objects(datapoint))

    def download(
        self,
        datapoint: xr.Dataset | UmbraStorageGranule,
        output_dir: Path | None = None,
        show_progress: bool = True,
        max_concurrent_downloads: int = 4,
    ) -> Path:
        """Download the data for a datapoint to the output directory or cache."""
        return _run(self._client.download(datapoint, output_dir, show_progress, max_concurrent_downloads))

    def download_objects(
        self,
        datapoint: xr.Dataset | UmbraStorageGranule,
        objects: list[str],
        output_dir: Path | None = None,
        show_progress: bool = True,
        max_concurrent_downloads: int = 4,
    ) -> Path:
        """Download selected objects, with names relative to the granule location."""
        return _run(
            self._client.download_objects(datapoint, objects, output_dir, show_progress, max_concurrent_downloads)
        )

    def delete(self, file_or_directory: Path) -> None:
        """Delete a product from the download cache."""
        _run(self._client.delete(file_or_directory))

    def destroy_cache(self) -> None:
        """Clear the download cache, deleting all entries."""
        _run(self._client.destroy_cache())


class CopernicusStorageClient:
    __module__ = "tilebox.storage"

    def __init__(
        self,
        access_key: str | None = None,
        secret_access_key: str | None = None,
        cache_directory: Path | None = Path.home() / ".cache" / "tilebox",
    ) -> None:
        """A tilebox storage client that downloads data from the Copernicus EO data.

        Args:
            access_key: The S3 Copernicus access key. If not provided, the AWS_ACCESS_KEY_ID environment
                variable will be used.
            secret_access_key: The S3 Copernicus secret access key. If not provided, the AWS_SECRET_ACCESS_KEY
                environment variable will be used.
            cache_directory: The directory to store downloaded data in. Defaults to ~/.cache/tilebox. If set to None
               no cache is used and the `output_dir` parameter will need be set when downloading data.
        """
        self._client = _CopernicusStorageClient(access_key, secret_access_key, cache_directory)

    def list_objects(self, datapoint: xr.Dataset | CopernicusStorageGranule) -> list[str]:
        """List object keys relative to the granule location."""
        return _run(self._client.list_objects(datapoint))

    def download(
        self,
        datapoint: xr.Dataset | CopernicusStorageGranule,
        output_dir: Path | None = None,
        show_progress: bool = True,
        max_concurrent_downloads: int = 4,
    ) -> Path:
        """Download the data for a datapoint to the output directory or cache."""
        return _run(self._client.download(datapoint, output_dir, show_progress, max_concurrent_downloads))

    def download_objects(
        self,
        datapoint: xr.Dataset | CopernicusStorageGranule,
        objects: list[str],
        output_dir: Path | None = None,
        show_progress: bool = True,
        max_concurrent_downloads: int = 4,
    ) -> Path:
        """Download selected objects, with names relative to the granule location."""
        return _run(
            self._client.download_objects(datapoint, objects, output_dir, show_progress, max_concurrent_downloads)
        )

    def download_quicklook(self, datapoint: xr.Dataset | CopernicusStorageGranule) -> Path:
        """Download the quicklook image for a datapoint."""
        return _run(self._client.download_quicklook(datapoint))

    def quicklook(self, datapoint: xr.Dataset | CopernicusStorageGranule, width: int = 600, height: int = 600) -> None:
        """Display the quicklook image in IPython."""
        _run(self._client.quicklook(datapoint, width, height))

    def delete(self, file_or_directory: Path) -> None:
        """Delete a product from the download cache."""
        _run(self._client.delete(file_or_directory))

    def destroy_cache(self) -> None:
        """Clear the download cache, deleting all entries."""
        _run(self._client.destroy_cache())


class USGSLandsatStorageClient:
    __module__ = "tilebox.storage"

    def __init__(self, cache_directory: Path | None = Path.home() / ".cache" / "tilebox") -> None:
        """A tilebox storage client that downloads data from the USGS Landsat S3 bucket.

        This client handles the requester-pays nature of the bucket and provides methods for listing and downloading
        data.

        Args:
            cache_directory: The directory to store downloaded data in. Defaults to ~/.cache/tilebox. If set to None
               no cache is used and the `output_dir` parameter will need be set when downloading data.
        """
        self._client = _USGSLandsatStorageClient(cache_directory)

    def list_objects(self, datapoint: xr.Dataset | USGSLandsatStorageGranule) -> list[str]:
        """List object keys relative to the granule location."""
        return _run(self._client.list_objects(datapoint))

    def download(
        self,
        datapoint: xr.Dataset | USGSLandsatStorageGranule,
        output_dir: Path | None = None,
        show_progress: bool = True,
        max_concurrent_downloads: int = 4,
    ) -> Path:
        """Download the data for a datapoint to the output directory or cache."""
        return _run(self._client.download(datapoint, output_dir, show_progress, max_concurrent_downloads))

    def download_objects(
        self,
        datapoint: xr.Dataset | USGSLandsatStorageGranule,
        objects: list[str],
        output_dir: Path | None = None,
        show_progress: bool = True,
        max_concurrent_downloads: int = 4,
    ) -> Path:
        """Download selected objects, with names relative to the granule location."""
        return _run(
            self._client.download_objects(datapoint, objects, output_dir, show_progress, max_concurrent_downloads)
        )

    def download_quicklook(self, datapoint: xr.Dataset | USGSLandsatStorageGranule) -> Path:
        """Download the quicklook image for a datapoint."""
        return _run(self._client.download_quicklook(datapoint))

    def quicklook(self, datapoint: xr.Dataset | USGSLandsatStorageGranule, width: int = 600, height: int = 600) -> None:
        """Display the quicklook image in IPython."""
        _run(self._client.quicklook(datapoint, width, height))

    def delete(self, file_or_directory: Path) -> None:
        """Delete a product from the download cache."""
        _run(self._client.delete(file_or_directory))

    def destroy_cache(self) -> None:
        """Clear the download cache, deleting all entries."""
        _run(self._client.destroy_cache())


class LocalFileSystemStorageClient:
    __module__ = "tilebox.storage"

    def __init__(self, root: Path) -> None:
        """A tilebox storage client for accessing data on a local file system, or a mounted network file system.

        Args:
            root: The root directory of the file system to access.
        """
        self._client = _LocalFileSystemStorageClient(root)

    def list_objects(self, datapoint: xr.Dataset | LocationStorageGranule) -> list[str]:
        """List object paths relative to the granule location."""
        return _run(self._client.list_objects(datapoint))

    def download(self, datapoint: xr.Dataset | LocationStorageGranule) -> Path:
        """Locate the data already on the local file system."""
        return _run(self._client.download(datapoint))

    def download_quicklook(self, datapoint: xr.Dataset | LocationStorageGranule) -> Path:
        """Locate the quicklook image already on the local file system."""
        return _run(self._client.download_quicklook(datapoint))

    def quicklook(self, datapoint: xr.Dataset | LocationStorageGranule, width: int = 600, height: int = 600) -> None:
        """Display the quicklook image in IPython."""
        _run(self._client.quicklook(datapoint, width, height))
