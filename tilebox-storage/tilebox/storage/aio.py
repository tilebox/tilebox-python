import asyncio
import hashlib
import os
import shutil
import tempfile
import zipfile
from asyncio import Queue, QueueEmpty
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any, TypeAlias

import anyio
import obstore as obs
import xarray as xr
from aiofile import async_open
from httpx import AsyncClient
from obstore.auth.boto3 import Boto3CredentialProvider
from obstore.store import GCSStore, LocalStore, S3Store
from tqdm.auto import tqdm

from _tilebox.grpc.aio.producer_consumer import async_producer_consumer
from _tilebox.grpc.aio.syncify import Syncifiable
from tilebox.storage.granule import (
    ASFStorageGranule,
    CopernicusStorageGranule,
    UmbraStorageGranule,
    USGSLandsatStorageGranule,
)
from tilebox.storage.providers import login

try:
    from IPython.display import HTML, Image, display  # type: ignore[assignment]
except ImportError:
    # IPython is not available, so we can't display the quicklook image
    # but let's define stubs for the type checker
    class Image:
        def __init__(*_args: Any, **_kwargs: Any) -> None: ...

    class HTML:
        def __init__(*_args: Any, **_kwargs: Any) -> None: ...

    def display(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("IPython is not available. Diagram can only be displayed in a notebook.")


ObjectStore: TypeAlias = S3Store | LocalStore | GCSStore


class _HttpClient(Syncifiable):
    def __init__(self, auth: dict[str, tuple[str, str]]) -> None:
        """A tilebox storage client that directly downloads files from the storage provider to a given directory."""
        self._clients: dict[str, AsyncClient] = {}
        self._auth = auth

    def __del__(self) -> None:
        for client in self._clients.values():
            asyncio.run(client.aclose())

    async def download_quicklook(
        self, datapoint: xr.Dataset | ASFStorageGranule, output_dir: Path | None = None
    ) -> Path:
        """Download the quicklook image for a given datapoint.

        Args:
            datapoint: The datapoint to download the quicklook for.
            output_dir: The directory to download the quicklook to. Defaults to the current working directory.

        Raises:
            ValueError: If no quicklook is available for the given datapoint.

        Returns:
            The path to the downloaded quicklook image.
        """
        granule = ASFStorageGranule.from_data(datapoint)
        image_data = await self._download_quicklook(granule)
        assert granule.urls.quicklook is not None  # otherwise download_quicklook would have raised a ValueError

        output_dir = output_dir or Path.cwd()
        output_dir.mkdir(parents=True, exist_ok=True)
        quicklook_file = output_dir / granule.urls.quicklook.rsplit("/", 1)[-1]
        async with async_open(quicklook_file, "wb") as f:
            await f.write(image_data)
        return quicklook_file

    async def quicklook(self, datapoint: xr.Dataset | ASFStorageGranule, width: int = 600, height: int = 600) -> None:
        """Display the quicklook image for a given datapoint.

        Requires an IPython kernel to be running. If you are not using IPython, use download_quicklook instead.

        Args:
            datapoint: The datapoint to download the quicklook for.
            width: Display width of the image in pixels. Defaults to 600.
            height: Display height of the image in pixels. Defaults to 600.

        Raises:
            ImportError: In case IPython is not available
            ValueError: If no quicklook is available for the given datapoint

        Returns:
            Image: The quicklook image.
        """
        granule = ASFStorageGranule.from_data(datapoint)
        image_data = await self._download_quicklook(granule)
        assert granule.urls.quicklook is not None  # otherwise _download_quicklook would have raised a ValueError
        image_name = granule.urls.quicklook.rsplit("/", 1)[-1]
        _display_quicklook(image_data, width, height, f"<code>Image {image_name} © ASF {granule.time.year}</code>")

    async def _download_quicklook(self, granule: ASFStorageGranule) -> bytes:
        """Download a granules quicklook image into a memory buffer."""
        if granule.urls.quicklook is None:
            raise ValueError("No quicklook available for this granule.")

        client = await self._client("ASF")
        response = await client.get(granule.urls.quicklook, follow_redirects=True)
        response.raise_for_status()
        return response.content

    async def download(
        self,
        datapoint: xr.Dataset | ASFStorageGranule,
        output_dir: Path | None = None,
        verify: bool = True,
        extract: bool = True,
        show_progress: bool = True,
    ) -> Path:
        """Download the data for a given datapoint, and optionally extract it.

        Args:
            datapoint: The datapoint to download the data for.
            output_dir: The directory to download the data to. Defaults to the current working directory.
            verify: Whether to verify the md5sum of the downloaded file. Defaults to True.
            extract: Whether to extract the downloaded file. Defaults to True.
            show_progress: Whether to show a progress bar while downloading. Defaults to True.

        Raises:
            ValueError: When attempting to extract a file that is not a zip file.

        Returns:
            Path: The path to the downloaded data file or directory.
        """
        granule = ASFStorageGranule.from_data(datapoint)

        data_file = await self._download_stream(granule, output_dir or Path.cwd(), verify, show_progress)
        if extract:
            if data_file.suffix != ".zip":
                raise ValueError("Failed to extract: The downloaded file is not a zip file.")
            data_dir = await self._extract(data_file)
            data_file.unlink()
            return data_dir
        return data_file

    async def _extract(self, zip_file: Path) -> Path:
        """Extract a zip file into the directory containing the zip file."""
        with zipfile.ZipFile(zip_file, "r") as file:
            name = file.namelist()[0]
            file.extractall(zip_file.parent)
        return zip_file.parent / name

    async def _download_stream(
        self, granule: ASFStorageGranule, output_dir: Path, verify: bool, show_progress: bool
    ) -> Path:
        """Chunked download of a file from the given url into the given directory.

        Args:
            granule: The granule to download.
            output_dir: The directory to download the file to.
            verify: Whether to verify the md5sum of the downloaded file.
            show_progress: Whether to show a progress bar while downloading.

        Raises:
            ValueError: When the md5sum of the downloaded file does not match the expected md5sum.

        Returns:
            Path: The downloaded file.
        """
        url = granule.urls.data

        # we download into a temporary file, which we then move to the final location once the download is complete
        # this way we can be sure that the files in the download location are complete and not partially downloaded
        _, download_file = tempfile.mkstemp(prefix="tilebox")

        async def downloader() -> AsyncIterator[bytes]:
            client = await self._client("ASF")
            async with client.stream("GET", url, follow_redirects=True) as response:
                response.raise_for_status()
                async for chunk in response.aiter_bytes():
                    yield chunk

        md5 = hashlib.md5() if verify else None  # noqa: S324
        progress = None
        if show_progress:
            progress = tqdm(total=granule.file_size, unit="B", unit_scale=True, unit_divisor=1024)

        async def writer(chunk: bytes) -> None:
            async with async_open(download_file, "ab") as f:
                await f.write(chunk)
                if md5 is not None:
                    md5.update(chunk)
                if progress is not None:
                    progress.update(len(chunk))

        await async_producer_consumer(downloader(), writer)

        if md5 is not None and md5.hexdigest() != granule.md5sum:
            raise ValueError("md5sum mismatch: The downloaded file is corrupted.")

        if progress is not None:
            progress.close()

        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / url.rsplit("/", 1)[-1]
        shutil.move(download_file, output_file)
        return output_file

    async def _client(self, storage_provider: str) -> AsyncClient:
        """Get an authenticated client for the given storage provider.

        Args:
            storage_provider: The storage provider to access the client for.

        Returns:
            The authenticated client for the given storage provider.
        """
        if storage_provider in self._clients:
            return self._clients[storage_provider]

        if storage_provider not in self._auth:
            raise ValueError(f"Missing credentials for storage provider '{storage_provider}'")

        auth = self._auth[storage_provider]
        client = await login(storage_provider, auth)
        self._clients[storage_provider] = client
        return client


def _display_quicklook(image_data: bytes | Path, width: int, height: int, image_caption: str | None = None) -> None:
    display(Image(image_data, width=width, height=height))
    if image_caption is not None:
        display(HTML(image_caption))


class StorageClient(Syncifiable):
    def __init__(self, cache_directory: Path | None) -> None:
        self._cache = cache_directory

    async def delete(self, file_or_directory: Path) -> None:
        """Delete a product from the download cache."""
        if file_or_directory.is_absolute():
            raise ValueError("Refusing to delete an absolute path from the cache.")
        if self._cache not in file_or_directory.parents:
            raise ValueError(f"Path '{file_or_directory}' is not inside the cache directory '{self._cache}'")
        shutil.rmtree(file_or_directory)

    async def destroy_cache(self) -> None:
        """Clear the download cache, deleting all entries."""
        if self._cache is not None:
            shutil.rmtree(self._cache)


async def list_object_paths(store: ObjectStore, prefix: str) -> list[str]:
    objects = await obs.list(store, prefix).collect_async()
    prefix_path = Path(prefix)
    return sorted(str(Path(obj["path"]).relative_to(prefix_path)) for obj in objects)


async def download_objects(  # noqa: PLR0913
    store: ObjectStore,
    prefix: str,
    objects: list[str],
    output_dir: Path,
    show_progress: bool = True,
    max_concurrent_downloads: int = 10,
) -> None:
    queue = Queue()
    for obj in objects:
        await queue.put((prefix, obj))

    max_concurrent_downloads = max(1, min(max_concurrent_downloads, len(objects)))
    async with anyio.create_task_group() as task_group:
        for _ in range(max_concurrent_downloads):
            task_group.start_soon(_download_worker, store, queue, output_dir, show_progress)


async def _download_worker(
    store: ObjectStore,
    queue: Queue[tuple[str, str]],
    output_dir: Path,
    show_progress: bool = True,
) -> None:
    while True:
        try:
            prefix, obj = queue.get_nowait()
        except QueueEmpty:
            break

        await _download_object(store, prefix, obj, output_dir, show_progress)


async def _download_object(
    store: ObjectStore, prefix: str, obj: str, output_dir: Path, show_progress: bool = True
) -> Path:
    key = str(Path(prefix) / obj)
    output_path = output_dir / obj
    if output_path.exists():  # already cached
        return output_path

    output_path.parent.mkdir(parents=True, exist_ok=True)
    download_path = output_path.parent / f"{output_path.name}.part"
    response = await obs.get_async(store, key)
    file_size = response.meta["size"]
    with download_path.open("wb") as f:
        if show_progress:
            with tqdm(desc=obj, total=file_size, unit="B", unit_scale=True, unit_divisor=1024) as progress:
                async for bytes_chunk in response:
                    f.write(bytes_chunk)
                    progress.update(len(bytes_chunk))
        else:
            async for bytes_chunk in response:
                f.write(bytes_chunk)

    shutil.move(download_path, output_path)
    return output_path


class ASFStorageClient(StorageClient):
    def __init__(self, user: str, password: str, cache_directory: Path = Path.home() / ".cache" / "tilebox") -> None:
        """A tilebox storage client that downloads data from the Alaska Satellite Facility.

        Args:
            user: The username to use for authentication.
            password: The password to use for authentication.
            cache_directory: The directory to store downloaded data in. Defaults to ~/.cache/tilebox. If set to None
               no cache is used and the `output_dir` parameter will need be set when downloading data.
        """
        super().__init__(cache_directory)
        self._client = _HttpClient({"ASF": (user, password)})

    async def download(
        self,
        datapoint: xr.Dataset | ASFStorageGranule,
        output_dir: Path | None = None,
        verify: bool = True,
        extract: bool = True,
        show_progress: bool = True,
    ) -> Path:
        """Download the data for a given datapoint, and optionally extract it.

        Args:
            datapoint: The datapoint to download the data for.
            output_dir: The directory to download the data to. Defaults to the cache directory.
            verify: Whether to verify the md5sum of the downloaded file. Defaults to True.
            extract: Whether to extract the downloaded file. Defaults to True.
            show_progress: Whether to show a progress bar while downloading. Defaults to True.

        Raises:
            ValueError: When attempting to extract a file that is not a zip file.

        Returns:
            Path: The path to the downloaded data file or directory.
        """
        granule = ASFStorageGranule.from_data(datapoint)
        url = granule.urls.data

        base_folder = output_dir or self._cache
        if base_folder is None:
            raise ValueError("No cache directory or output directory provided.")
        output_zip_file = base_folder / "ASF" / granule.granule_name / url.rsplit("/", 1)[-1]

        if not extract:  # we want just the zip file, not the extracted one:
            if output_zip_file.exists():  # we already have the zip file cached
                return output_zip_file
            # we don't have it cached: download the zip file
            return await self._client.download(datapoint, output_zip_file.parent, verify, extract, show_progress)

        # we want the extracted data, not the zip file:
        output_dir = output_zip_file.parent / output_zip_file.stem
        if output_dir.exists():  # we already have the extracted data cached
            return output_dir
        if output_zip_file.exists():  # we have the zip file cached, but not the extracted data
            return await self._client._extract(output_zip_file)  # noqa: SLF001
        # we have nothing cached: download and extract zip file
        return await self._client.download(datapoint, output_zip_file.parent, verify, extract, show_progress)

    async def download_quicklook(self, datapoint: xr.Dataset | ASFStorageGranule) -> Path:
        """Download the quicklook image for a given datapoint.

        Args:
            datapoint: The datapoint to download the quicklook for.

        Raises:
            ValueError: If no quicklook is available for the given datapoint.

        Returns:
            The path to the downloaded quicklook image.
        """
        return await self._download_quicklook(datapoint)

    async def quicklook(self, datapoint: xr.Dataset | ASFStorageGranule, width: int = 600, height: int = 600) -> None:
        """Display the quicklook image for a given datapoint.

        Requires an IPython kernel to be running. If you are not using IPython, use download_quicklook instead.

        Args:
            datapoint: The datapoint to download the quicklook for.
            width: Display width of the image in pixels. Defaults to 600.
            height: Display height of the image in pixels. Defaults to 600.

        Raises:
            ImportError: In case IPython is not available.
            ValueError: If no quicklook is available for the given datapoint.

        Returns:
            Image: The quicklook image.
        """
        granule = ASFStorageGranule.from_data(datapoint)
        if Image is None:
            raise ImportError("IPython is not available, please use download_preview instead.")
        quicklook = await self._download_quicklook(datapoint)
        _display_quicklook(quicklook, width, height, f"<code>Image {quicklook.name} © ASF {granule.time.year}</code>")

    async def _download_quicklook(self, datapoint: xr.Dataset | ASFStorageGranule) -> Path:
        granule = ASFStorageGranule.from_data(datapoint)
        if (url := granule.urls.quicklook) is None:
            raise ValueError("No quicklook available for this granule.")

        if self._cache is None:
            output_file = tempfile.NamedTemporaryFile(prefix="tilebox", delete=False)  # noqa: SIM115
        else:
            output_file = self._cache / "ASF" / granule.granule_name / url.rsplit("/", 1)[-1]
            if output_file.exists():
                return output_file

        return await self._client.download_quicklook(datapoint, output_file.parent)


def _umbra_s3_prefix(datapoint: xr.Dataset | UmbraStorageGranule) -> str:
    granule = UmbraStorageGranule.from_data(datapoint)
    return f"sar-data/tasks/{granule.location}/"


class UmbraStorageClient(StorageClient):
    _STORAGE_PROVIDER = "Umbra"
    _BUCKET = "umbra-open-data-catalog"
    _REGION = "us-west-2"

    def __init__(self, cache_directory: Path | None = Path.home() / ".cache" / "tilebox") -> None:
        """A tilebox storage client that downloads data from the Umbra Open Data Catalog.

        Args:
            cache_directory: The directory to store downloaded data in. Defaults to ~/.cache/tilebox. If set to None
               no cache is used and the `output_dir` parameter will need be set when downloading data.
        """
        super().__init__(cache_directory)

        self._store: ObjectStore = S3Store(self._BUCKET, region=self._REGION, skip_signature=True)

    async def list_objects(self, datapoint: xr.Dataset | UmbraStorageGranule) -> list[str]:
        """List all available objects for a given datapoint.

        Args:
            datapoint: The datapoint to list available objects the data for.

        Returns:
            List of object keys available for the given datapoint, relative to the granule location."""
        return await list_object_paths(self._store, _umbra_s3_prefix(datapoint))

    async def download(
        self,
        datapoint: xr.Dataset | UmbraStorageGranule,
        output_dir: Path | None = None,
        show_progress: bool = True,
        max_concurrent_downloads: int = 4,
    ) -> Path:
        """Download the data for a given datapoint.

        Args:
            datapoint: The datapoint to download the data for.
            output_dir: The directory to download the data to. Optional, defaults to the cache directory.
            show_progress: Whether to show a progress bar while downloading. Defaults to True.
            max_concurrent_downloads: The maximum number of concurrent downloads. Defaults to 4.

        Returns:
            The path to the downloaded data directory.
        """
        all_objects = await list_object_paths(self._store, _umbra_s3_prefix(datapoint))
        return await self._download_objects(datapoint, all_objects, output_dir, show_progress, max_concurrent_downloads)

    async def download_objects(
        self,
        datapoint: xr.Dataset | UmbraStorageGranule,
        objects: list[str],
        output_dir: Path | None = None,
        show_progress: bool = True,
        max_concurrent_downloads: int = 4,
    ) -> Path:
        """Download a subset of the data for a given datapoint.

        Typically used in conjunction with list_objects to filter the available objects beforehand.

        Args:
            datapoint: The datapoint to download the data for.
            objects: A list of objects to download. Only objects that are in this list will be downloaded. See
                list_objects to get a list of available objects to filter on. Object names are considered relative
                to the granule location.
            output_dir: The directory to download the data to. Optional, defaults to the cache directory.
            show_progress: Whether to show a progress bar while downloading. Defaults to True.
            max_concurrent_downloads: The maximum number of concurrent downloads. Defaults to 4.

        Returns:
            The path to the downloaded data directory.
        """
        return await self._download_objects(datapoint, objects, output_dir, show_progress, max_concurrent_downloads)

    async def _download_objects(
        self,
        datapoint: xr.Dataset | UmbraStorageGranule,
        objects: list[str],
        output_dir: Path | None = None,
        show_progress: bool = True,
        max_concurrent_downloads: int = 4,
    ) -> Path:
        prefix = _umbra_s3_prefix(datapoint)

        base_folder = output_dir or self._cache
        if base_folder is None:
            raise ValueError("No cache directory or output directory provided.")
        output_folder = base_folder / self._STORAGE_PROVIDER / Path(prefix)

        if len(objects) == 0:
            return output_folder

        await download_objects(self._store, prefix, objects, output_folder, show_progress, max_concurrent_downloads)
        return output_folder


def _copernicus_s3_prefix(datapoint: xr.Dataset | CopernicusStorageGranule) -> str:
    granule = CopernicusStorageGranule.from_data(datapoint)
    return granule.location.removeprefix("/eodata/")


class CopernicusStorageClient(StorageClient):
    _STORAGE_PROVIDER = "CopernicusDataspace"
    _BUCKET = "eodata"
    _ENDPOINT_URL = "https://eodata.dataspace.copernicus.eu"
    _ACCESS_KEY_ID_ENV_VAR = "AWS_ACCESS_KEY_ID"
    _SECRET_ACCESS_KEY_ENV_VAR = "AWS_SECRET_ACCESS_KEY"  # noqa: S105

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
        super().__init__(cache_directory)
        if access_key is None:
            access_key = os.environ.get(self._ACCESS_KEY_ID_ENV_VAR, None)
        if secret_access_key is None:
            secret_access_key = os.environ.get(self._SECRET_ACCESS_KEY_ENV_VAR, None)

        if access_key is None:
            raise ValueError(
                f"No access key provided and no {self._ACCESS_KEY_ID_ENV_VAR} environment variable set. Please "
                f"specify a dataset using the access_key argument or the environment variable."
                f"To get access to the Copernicus data, please visit: https://documentation.dataspace.copernicus.eu/APIs/S3.html"
            )
        if secret_access_key is None:
            raise ValueError(
                f"No secret access key provided and no {self._SECRET_ACCESS_KEY_ENV_VAR} environment variable set. Please "
                f"specify a dataset using the secret_access_key argument or the environment variable."
                f"To get access to the Copernicus data, please visit: https://documentation.dataspace.copernicus.eu/APIs/S3.html"
            )

        self._store = S3Store(
            bucket=self._BUCKET,
            endpoint=self._ENDPOINT_URL,
            access_key_id=access_key,
            secret_access_key=secret_access_key,
        )

    async def list_objects(self, datapoint: xr.Dataset | CopernicusStorageGranule) -> list[str]:
        """List all available objects for a given datapoint.

        Args:
            datapoint: The datapoint to list available objects the data for.

        Returns:
            List of object keys available for the given datapoint, relative to the granule location."""
        return await self._list_objects(datapoint)

    async def _list_objects(self, datapoint: xr.Dataset | CopernicusStorageGranule) -> list[str]:
        """List all available objects for a given datapoint.

        Args:
            datapoint: The datapoint to list available objects the data for.

        Returns:
            List of object keys available for the given datapoint, relative to the granule location."""

        granule = CopernicusStorageGranule.from_data(datapoint)
        # special handling for Sentinel-5P, where the location is not a folder but a single file
        if granule.location.endswith(".nc"):
            return [Path(granule.granule_name).name]

        return await list_object_paths(self._store, _copernicus_s3_prefix(granule))

    async def download(
        self,
        datapoint: xr.Dataset | CopernicusStorageGranule,
        output_dir: Path | None = None,
        show_progress: bool = True,
        max_concurrent_downloads: int = 4,
    ) -> Path:
        """Download the data for a given datapoint.

        Args:
            datapoint: The datapoint to download the data for.
            output_dir: The directory to download the data to. Optional, defaults to the cache directory.
            show_progress: Whether to show a progress bar while downloading. Defaults to True.
            max_concurrent_downloads: The maximum number of concurrent downloads. Defaults to 4.

        Returns:
            The path to the downloaded data directory.
        """
        granule = CopernicusStorageGranule.from_data(datapoint)

        all_objects = await self._list_objects(granule)
        return await self._download_objects(granule, all_objects, output_dir, show_progress, max_concurrent_downloads)

    async def download_objects(
        self,
        datapoint: xr.Dataset | CopernicusStorageGranule,
        objects: list[str],
        output_dir: Path | None = None,
        show_progress: bool = True,
        max_concurrent_downloads: int = 4,
    ) -> Path:
        """Download a subset of the data for a given datapoint.

        Typically used in conjunction with list_objects to filter the available objects beforehand.

        Args:
            datapoint: The datapoint to download the data for.
            objects: A list of objects to download. Only objects that are in this list will be downloaded. See
                list_objects to get a list of available objects to filter on. Object names are considered relative
                to the granule location.
            output_dir: The directory to download the data to. Optional, defaults to the cache directory.
            show_progress: Whether to show a progress bar while downloading. Defaults to True.
            max_concurrent_downloads: The maximum number of concurrent downloads. Defaults to 4.

        Returns:
            The path to the downloaded data directory.
        """
        return await self._download_objects(datapoint, objects, output_dir, show_progress, max_concurrent_downloads)

    async def _download_objects(
        self,
        datapoint: xr.Dataset | CopernicusStorageGranule,
        objects: list[str],
        output_dir: Path | None = None,
        show_progress: bool = True,
        max_concurrent_downloads: int = 4,
    ) -> Path:
        granule = CopernicusStorageGranule.from_data(datapoint)
        prefix = _copernicus_s3_prefix(granule)
        single_file = False

        # special handling for Sentinel-5P, where the location is not a folder but a single file
        if granule.location.endswith(".nc"):
            single_file = True
            prefix = str(Path(prefix).parent)

        base_folder = output_dir or self._cache
        if base_folder is None:
            raise ValueError("No cache directory or output directory provided.")
        output_folder = base_folder / self._STORAGE_PROVIDER / Path(prefix)

        if len(objects) == 0:
            return output_folder

        await download_objects(self._store, prefix, objects, output_folder, show_progress, max_concurrent_downloads)
        if single_file:
            return output_folder / objects[0]
        return output_folder

    async def download_quicklook(self, datapoint: xr.Dataset | CopernicusStorageGranule) -> Path:
        """Download the quicklook image for a given datapoint.

        Args:
            datapoint: The datapoint to download the quicklook for.

        Raises:
            ValueError: If no quicklook is available for the given datapoint.

        Returns:
            The path to the downloaded quicklook image.
        """
        return await self._download_quicklook(datapoint)

    async def quicklook(
        self, datapoint: xr.Dataset | CopernicusStorageGranule, width: int = 600, height: int = 600
    ) -> None:
        """Display the quicklook image for a given datapoint.

        Requires an IPython kernel to be running. If you are not using IPython, use download_quicklook instead.

        Args:
            datapoint: The datapoint to download the quicklook for.
            width: Display width of the image in pixels. Defaults to 600.
            height: Display height of the image in pixels. Defaults to 600.

        Raises:
            ImportError: In case IPython is not available.
            ValueError: If no quicklook is available for the given datapoint.
        """
        if Image is None:
            raise ImportError("IPython is not available, please use download_preview instead.")
        granule = CopernicusStorageGranule.from_data(datapoint)
        quicklook = await self._download_quicklook(granule)
        _display_quicklook(quicklook, width, height, f"<code>{granule.granule_name} © ESA {granule.time.year}</code>")

    async def _download_quicklook(self, datapoint: xr.Dataset | CopernicusStorageGranule) -> Path:
        granule = CopernicusStorageGranule.from_data(datapoint)
        if granule.thumbnail is None:
            raise ValueError(f"No quicklook available for {granule.granule_name}")

        prefix = _copernicus_s3_prefix(granule)
        output_folder = (
            self._cache / self._STORAGE_PROVIDER / Path(prefix)
            if self._cache is not None
            else Path.cwd() / self._STORAGE_PROVIDER
        )

        await download_objects(self._store, prefix, [granule.thumbnail], output_folder, show_progress=False)
        return output_folder / granule.thumbnail


def _landsat_s3_prefix(datapoint: xr.Dataset | USGSLandsatStorageGranule) -> str:
    granule = USGSLandsatStorageGranule.from_data(datapoint)
    return granule.location.removeprefix("s3://usgs-landsat/")


class USGSLandsatStorageClient(StorageClient):
    """
    A client for downloading USGS Landsat data from the usgs-landsat and usgs-landsat-ard S3 bucket.

    This client handles the requester-pays nature of the bucket and provides methods for listing and downloading data.
    """

    _STORAGE_PROVIDER = "USGSLandsat"
    _BUCKET = "usgs-landsat"
    _REGION = "us-west-2"

    def __init__(self, cache_directory: Path | None = Path.home() / ".cache" / "tilebox") -> None:
        """A tilebox storage client that downloads data from the USGS Landsat S3 bucket.

        Args:
            cache_directory: The directory to store downloaded data in. Defaults to ~/.cache/tilebox. If set to None
               no cache is used and the `output_dir` parameter will need be set when downloading data.
        """
        super().__init__(cache_directory)

        self._store = S3Store(
            self._BUCKET, region=self._REGION, request_payer=True, credential_provider=Boto3CredentialProvider()
        )

    async def list_objects(self, datapoint: xr.Dataset | USGSLandsatStorageGranule) -> list[str]:
        """List all available objects for a given datapoint.

        Args:
            datapoint: The datapoint to list available objects the data for.

        Returns:
            List of object keys available for the given datapoint, relative to the granule location."""
        return await list_object_paths(self._store, _landsat_s3_prefix(datapoint))

    async def download(
        self,
        datapoint: xr.Dataset | USGSLandsatStorageGranule,
        output_dir: Path | None = None,
        show_progress: bool = True,
        max_concurrent_downloads: int = 4,
    ) -> Path:
        """Download the data for a given datapoint.

        Args:
            datapoint: The datapoint to download the data for.
            output_dir: The directory to download the data to. Optional, defaults to the cache directory.
            show_progress: Whether to show a progress bar while downloading. Defaults to True.
            max_concurrent_downloads: The maximum number of concurrent downloads. Defaults to 4.

        Returns:
            The path to the downloaded data directory.
        """
        all_objects = await list_object_paths(self._store, _landsat_s3_prefix(datapoint))
        return await self._download_objects(datapoint, all_objects, output_dir, show_progress, max_concurrent_downloads)

    async def download_objects(
        self,
        datapoint: xr.Dataset | USGSLandsatStorageGranule,
        objects: list[str],
        output_dir: Path | None = None,
        show_progress: bool = True,
        max_concurrent_downloads: int = 4,
    ) -> Path:
        """Download a subset of the data for a given datapoint.

        Typically used in conjunction with list_objects to filter the available objects beforehand.

        Args:
            datapoint: The datapoint to download the data for.
            objects: A list of objects to download. Only objects that are in this list will be downloaded. See
                list_objects to get a list of available objects to filter on. Object names are considered relative
                to the granule location.
            output_dir: The directory to download the data to. Optional, defaults to the cache directory.
            show_progress: Whether to show a progress bar while downloading. Defaults to True.
            max_concurrent_downloads: The maximum number of concurrent downloads. Defaults to 4.

        Returns:
            The path to the downloaded data directory.
        """
        return await self._download_objects(datapoint, objects, output_dir, show_progress, max_concurrent_downloads)

    async def _download_objects(
        self,
        datapoint: xr.Dataset | USGSLandsatStorageGranule,
        objects: list[str],
        output_dir: Path | None = None,
        show_progress: bool = True,
        max_concurrent_downloads: int = 4,
    ) -> Path:
        prefix = _landsat_s3_prefix(datapoint)

        base_folder = output_dir or self._cache
        if base_folder is None:
            raise ValueError("No cache directory or output directory provided.")
        output_folder = base_folder / Path(prefix)

        if len(objects) == 0:
            return output_folder

        await download_objects(self._store, prefix, objects, output_folder, show_progress, max_concurrent_downloads)
        return output_folder

    async def download_quicklook(self, datapoint: xr.Dataset | USGSLandsatStorageGranule) -> Path:
        """Download the quicklook image for a given datapoint.

        Args:
            datapoint: The datapoint to download the quicklook for.

        Raises:
            ValueError: If no quicklook is available for the given datapoint.

        Returns:
            The path to the downloaded quicklook image.
        """
        return await self._download_quicklook(datapoint)

    async def quicklook(
        self, datapoint: xr.Dataset | USGSLandsatStorageGranule, width: int = 600, height: int = 600
    ) -> None:
        """Display the quicklook image for a given datapoint.

        Requires an IPython kernel to be running. If you are not using IPython, use download_quicklook instead.

        Args:
            datapoint: The datapoint to download the quicklook for.
            width: Display width of the image in pixels. Defaults to 600.
            height: Display height of the image in pixels. Defaults to 600.

        Raises:
            ImportError: In case IPython is not available.
            ValueError: If no quicklook is available for the given datapoint.
        """
        if Image is None:
            raise ImportError("IPython is not available, please use download_preview instead.")
        quicklook = await self._download_quicklook(datapoint)
        _display_quicklook(quicklook, width, height, f"<code>Image {quicklook.name} © USGS</code>")

    async def _download_quicklook(self, datapoint: xr.Dataset | USGSLandsatStorageGranule) -> Path:
        granule = USGSLandsatStorageGranule.from_data(datapoint)
        if granule.thumbnail is None:
            raise ValueError(f"No quicklook available for {granule.granule_name}")

        prefix = _landsat_s3_prefix(datapoint)
        output_folder = (
            self._cache / self._STORAGE_PROVIDER / Path(prefix)
            if self._cache is not None
            else Path.cwd() / self._STORAGE_PROVIDER
        )

        await download_objects(self._store, prefix, [granule.thumbnail], output_folder, show_progress=False)
        return output_folder / granule.thumbnail
