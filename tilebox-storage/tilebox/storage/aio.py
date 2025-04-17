import hashlib
import os
import shutil
import tempfile
import warnings
import zipfile
from collections.abc import AsyncIterator, Callable, Iterator
from pathlib import Path
from typing import IO, Any

import anyio
import boto3
from aiofile import async_open
from botocore import UNSIGNED
from botocore.client import Config
from httpx import AsyncClient
from mypy_boto3_s3 import S3Client
from mypy_boto3_s3.type_defs import ObjectTypeDef
from tqdm.auto import tqdm

from _tilebox.grpc.aio.producer_consumer import async_producer_consumer
from _tilebox.grpc.aio.syncify import Syncifiable
from tilebox.storage.granule import ASFStorageGranule, CopernicusStorageGranule, UmbraStorageGranule
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


import xarray as xr


class _HttpClient(Syncifiable):
    def __init__(self, auth: dict[str, tuple[str, str]]) -> None:
        """A tilebox storage client that directly downloads files from the storage provider to a given directory."""
        self._clients: dict[str, AsyncClient] = {}
        self._auth = auth

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
        _display_quicklook(image_data, image_name, granule.time.year, width, height)

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


def _display_quicklook(image_data: bytes | Path, image_name: str, year: int, width: int, height: int) -> None:
    display(Image(image_data, width=width, height=height))
    image_copyright = HTML(f"<code>Image {image_name} © ESA {year}</code>")
    display(image_copyright)


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
        _display_quicklook(quicklook, quicklook.name, granule.time.year, width, height)

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


class _S3Client:
    def __init__(self, s3: S3Client, bucket: str) -> None:
        self._bucket = bucket
        self._s3 = s3

    def list_objects(self, prefix: str) -> Iterator[ObjectTypeDef]:
        """Returns an iterator over the objects in the S3 bucket that starts with the given prefix."""
        paginator = self._s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self._bucket, Prefix=prefix):
            yield from page.get("Contents", [])

    async def download_object(  # noqa: PLR0913
        self, key: str, name: str, size: int, download_file: IO[Any], verify: bool, show_progress: bool
    ) -> None:
        """Download an object from S3 into a file."""
        progress = None
        if show_progress:
            progress = tqdm(
                desc=name,
                total=size,
                unit="B",
                unit_scale=True,
                unit_divisor=1024,
            )

        self._s3.download_fileobj(
            Bucket=self._bucket,
            Key=key,
            Fileobj=download_file,
            ExtraArgs={"ChecksumMode": "ENABLED"} if verify else None,
            Callback=progress.update if progress else None,
        )

        if progress is not None:
            if progress.total != progress.n:
                progress.n = progress.total
                progress.refresh()
            progress.close()


class UmbraStorageClient(StorageClient):
    _STORAGE_PROVIDER = "Umbra"
    _BUCKET = "umbra-open-data-catalog"

    def __init__(self, cache_directory: Path | None = Path.home() / ".cache" / "tilebox") -> None:
        """A tilebox storage client that downloads data from the Umbra Open Data Catalog.

        Args:
            cache_directory: The directory to store downloaded data in. Defaults to ~/.cache/tilebox. If set to None
               no cache is used and the `output_dir` parameter will need be set when downloading data.
        """
        super().__init__(cache_directory)

        with warnings.catch_warnings():
            # https://github.com/boto/boto3/issues/3889
            warnings.filterwarnings("ignore", category=DeprecationWarning, message=".*datetime.utcnow.*")
            boto3_client = boto3.client("s3", config=Config(signature_version=UNSIGNED))

        self._s3 = _S3Client(s3=boto3_client, bucket=self._BUCKET)

    def list_objects(self, datapoint: xr.Dataset | UmbraStorageGranule) -> list[str]:
        """List all available objects for a given datapoint.

        Args:
            datapoint: The datapoint to list available objects the data for.

        Returns:
            List of object keys available for the given datapoint, relative to the granule location."""
        granule = UmbraStorageGranule.from_data(datapoint)
        prefix = f"sar-data/tasks/{granule.location}/"
        keys = [object_metadata.get("Key") for object_metadata in self._s3.list_objects(prefix)]
        return [k.removeprefix(prefix) for k in keys if k is not None]

    async def download(
        self,
        datapoint: xr.Dataset | UmbraStorageGranule,
        output_dir: Path | None = None,
        verify: bool = True,
        show_progress: bool = True,
    ) -> Path:
        """Download the data for a given datapoint.

        Args:
            datapoint: The datapoint to download the data for.
            output_dir: The directory to download the data to. Optional, defaults to the cache directory.
            verify: Whether to verify the md5sum of the downloaded file. Defaults to True.
            show_progress: Whether to show a progress bar while downloading. Defaults to True.

        Returns:
            The path to the downloaded data directory.
        """
        return await self._download(datapoint, None, output_dir, verify, show_progress)

    async def download_objects(
        self,
        datapoint: xr.Dataset | UmbraStorageGranule,
        objects: list[str],
        output_dir: Path | None = None,
        verify: bool = True,
        show_progress: bool = True,
    ) -> Path:
        """Download a subset of the data for a given datapoint.

        Typically used in conjunction with list_objects to filter the available objects beforehand.

        Args:
            datapoint: The datapoint to download the data for.
            objects: A list of objects to download. Only objects that are in this list will be downloaded. See
                list_objects to get a list of available objects to filter on. Object names are considered relative
                to the granule location.
            output_dir: The directory to download the data to. Optional, defaults to the cache directory.
            verify: Whether to verify the md5sum of the downloaded file. Defaults to True.
            show_progress: Whether to show a progress bar while downloading. Defaults to True.

        Returns:
            The path to the downloaded data directory.
        """
        return await self._download(datapoint, lambda key: key in objects, output_dir, verify, show_progress)

    async def _download(
        self,
        datapoint: xr.Dataset | UmbraStorageGranule,
        obj_filter_func: Callable[[str], bool] | None = None,
        output_dir: Path | None = None,
        verify: bool = True,
        show_progress: bool = True,
    ) -> Path:
        granule = UmbraStorageGranule.from_data(datapoint)

        base_folder = output_dir or self._cache
        if base_folder is None:
            raise ValueError("No cache directory or output directory provided.")
        output_folder = base_folder / self._STORAGE_PROVIDER / granule.location

        prefix = f"sar-data/tasks/{granule.location}/"

        objects = self._s3.list_objects(prefix)
        objects = [obj for obj in objects if "Key" in obj]  # Key is optional, so just in case filter out obj without

        if obj_filter_func is not None:
            # get object names relative to the granule location, so we can pass it to our filter function
            object_names = [obj["Key"].removeprefix(prefix) for obj in objects if "Key" in obj]
            objects = [
                object_metadata
                for (object_metadata, object_name) in zip(objects, object_names, strict=True)
                if obj_filter_func(object_name)
            ]

        async with anyio.create_task_group() as task_group:
            for object_metadata in objects:
                task_group.start_soon(
                    self._download_object, object_metadata, prefix, output_folder, verify, show_progress
                )

        return output_folder

    async def _download_object(
        self, object_metadata: ObjectTypeDef, prefix: str, output_folder: Path, verify: bool, show_progress: bool
    ) -> None:
        key = object_metadata.get("Key", "")
        relative_path = key.removeprefix(prefix)
        if relative_path.removeprefix("/") == "":  # skip the root folder if it shows up in the list for some reason
            return
        if object_metadata.get("Size", 0) == 0:  # skip empty objects (they are just folder markers)
            return

        output_file = output_folder / relative_path
        if output_file.exists():
            return

        # we download into a temporary file, which we then move to the final location once the download is complete
        # this way we can be sure that the files in the download location are complete and not partially downloaded
        with tempfile.NamedTemporaryFile(prefix="tilebox", delete=False) as download_file:
            await self._s3.download_object(
                key,
                # as "name" for the progress bar we display the relative path to the root of the download
                relative_path,
                object_metadata.get("Size", 0),
                download_file,
                verify,
                show_progress,
            )

            output_folder.mkdir(parents=True, exist_ok=True)
            shutil.move(download_file.name, output_file)


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

        with warnings.catch_warnings():
            # https://github.com/boto/boto3/issues/3889
            warnings.filterwarnings("ignore", category=DeprecationWarning, message=".*datetime.utcnow.*")
            boto3_client = boto3.client(
                "s3",
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_access_key,
                endpoint_url=self._ENDPOINT_URL,
            )

        self._s3 = _S3Client(
            s3=boto3_client,
            bucket=self._BUCKET,
        )

    def list_objects(self, datapoint: xr.Dataset | CopernicusStorageGranule) -> list[str]:
        """List all available objects for a given datapoint.

        Args:
            datapoint: The datapoint to list available objects the data for.

        Returns:
            List of object keys available for the given datapoint, relative to the granule location."""
        granule = CopernicusStorageGranule.from_data(datapoint)
        prefix = granule.location.removeprefix("/eodata/") + "/"
        keys = [object_metadata.get("Key") for object_metadata in self._s3.list_objects(prefix)]
        return [k.removeprefix(prefix) for k in keys if k is not None]

    async def download(
        self,
        datapoint: xr.Dataset | CopernicusStorageGranule,
        output_dir: Path | None = None,
        verify: bool = True,
        show_progress: bool = True,
    ) -> Path:
        """Download the data for a given datapoint.

        Args:
            datapoint: The datapoint to download the data for.
            output_dir: The directory to download the data to. Optional, defaults to the cache directory.
            verify: Whether to verify the md5sum of the downloaded file. Defaults to True.
            show_progress: Whether to show a progress bar while downloading. Defaults to True.

        Returns:
            The path to the downloaded data directory.
        """
        return await self._download(datapoint, None, output_dir, verify, show_progress)

    async def download_objects(
        self,
        datapoint: xr.Dataset | CopernicusStorageGranule,
        objects: list[str],
        output_dir: Path | None = None,
        verify: bool = True,
        show_progress: bool = True,
    ) -> Path:
        """Download a subset of the data for a given datapoint.

        Typically used in conjunction with list_objects to filter the available objects beforehand.

        Args:
            datapoint: The datapoint to download the data for.
            objects: A list of objects to download. Only objects that are in this list will be downloaded. See
                list_objects to get a list of available objects to filter on. Object names are considered relative
                to the granule location.
            output_dir: The directory to download the data to. Optional, defaults to the cache directory.
            verify: Whether to verify the md5sum of the downloaded file. Defaults to True.
            show_progress: Whether to show a progress bar while downloading. Defaults to True.

        Returns:
            The path to the downloaded data directory.
        """
        return await self._download(datapoint, lambda key: key in objects, output_dir, verify, show_progress)

    async def _download(
        self,
        datapoint: xr.Dataset | CopernicusStorageGranule,
        obj_filter_func: Callable[[str], bool] | None = None,
        output_dir: Path | None = None,
        verify: bool = True,
        show_progress: bool = True,
    ) -> Path:
        granule = CopernicusStorageGranule.from_data(datapoint)

        base_folder = output_dir or self._cache
        if base_folder is None:
            raise ValueError("No cache directory or output directory provided.")
        output_folder = base_folder / Path(granule.location.removeprefix("/eodata/"))

        prefix = granule.location.removeprefix("/eodata/") + "/"
        objects = self._s3.list_objects(prefix)
        objects = [obj for obj in objects if "Key" in obj]  # Key is optional, so just in case filter out obj without

        if obj_filter_func is not None:
            # get object names relative to the granule location, so we can pass it to our filter function
            object_names = [obj["Key"].removeprefix(prefix) for obj in objects if "Key" in obj]
            objects = [
                object_metadata
                for (object_metadata, object_name) in zip(objects, object_names, strict=True)
                if obj_filter_func(object_name)
            ]

        async with anyio.create_task_group() as task_group:
            # even though this is a async task group, the downloads are still synchronous
            # because the S3 client is synchronous
            # we could work around this by using anyio.to_thread.run_sync
            # but then we download all files in parallel, which might be too much
            for object_metadata in objects:
                task_group.start_soon(
                    self._download_object, object_metadata, prefix, output_folder, verify, show_progress
                )

        return output_folder

    async def _download_object(
        self, object_metadata: ObjectTypeDef, prefix: str, output_folder: Path, verify: bool, show_progress: bool
    ) -> None:
        key = object_metadata.get("Key", "")
        relative_path = key.removeprefix(prefix)
        if relative_path.removeprefix("/") == "":  # skip the root folder if it shows up in the list for some reason
            return
        if object_metadata.get("Size", 0) == 0:  # skip empty objects (they are just folder markers)
            return

        output_file = output_folder / relative_path
        if output_file.exists():
            return

        # we download into a temporary file, which we then move to the final location once the download is complete
        # this way we can be sure that the files in the download location are complete and not partially downloaded
        with tempfile.NamedTemporaryFile(prefix="tilebox", delete=False) as download_file:
            await self._s3.download_object(
                key,
                # as "name" for the progress bar we display the relative path to the root of the download
                relative_path,
                object_metadata.get("Size", 0),
                download_file,
                verify,
                show_progress,
            )

            output_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(download_file.name, output_file)
