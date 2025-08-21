from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import xarray as xr

from tilebox.storage.providers import StorageURLs


@dataclass
class ASFStorageGranule:
    time: datetime
    granule_name: str
    file_size: int
    md5sum: str
    urls: StorageURLs

    @classmethod
    def from_data(cls, dataset: "xr.Dataset | ASFStorageGranule") -> "ASFStorageGranule":
        """Extract the granule information from a datapoint given as xarray dataset."""
        if isinstance(dataset, ASFStorageGranule):
            return dataset

        if "time" in dataset.dims:
            if dataset.sizes["time"] == 1:
                dataset = dataset.isel(time=0)
            else:
                raise ValueError("The given dataset has more than one granule.")

        granule_name = dataset.granule_name.item()
        quicklook_available = "quicklook_available" in dataset and dataset.quicklook_available.item()

        urls = _asf_download_urls(granule_name)

        if not quicklook_available and urls.quicklook is not None:
            urls = StorageURLs(urls.data, None)

        time = datetime.combine(dataset.time.dt.date.item(), dataset.time.dt.time.item())

        return cls(
            time,
            granule_name,
            dataset.file_size.item(),
            dataset.md5sum.item(),
            urls,
        )


# ASF - Alaska Satellite Facility
_ASF_URL = "https://datapool.asf.alaska.edu"


def _asf_download_urls(granule_name: str) -> StorageURLs:
    platform = granule_name.split("_")[0]
    file_name = granule_name
    processing_level = "L0"
    quicklook = None
    quicklook = f"{_ASF_URL}/BROWSE/{platform}/{granule_name}.jpg"
    file_name = file_name.replace("STD_", f"STD_{processing_level}_")
    data = f"{_ASF_URL}/{processing_level}/{platform}/{file_name}.zip"
    return StorageURLs(data, quicklook)


@dataclass
class UmbraStorageGranule:
    time: datetime
    granule_name: str
    location: str

    @classmethod
    def from_data(cls, dataset: "xr.Dataset | UmbraStorageGranule") -> "UmbraStorageGranule":
        """Extract the granule information from a datapoint given as xarray dataset."""
        if isinstance(dataset, UmbraStorageGranule):
            return dataset

        if "time" in dataset.dims:
            if dataset.sizes["time"] == 1:
                dataset = dataset.isel(time=0)
            else:
                raise ValueError("The given dataset has more than one granule.")

        time = datetime.combine(dataset.time.dt.date.item(), dataset.time.dt.time.item())

        return cls(
            time,
            dataset.granule_name.item(),
            dataset.location.item(),
        )


def _thumbnail_relative_to_eodata_location(thumbnail_url: str, location: str) -> str:
    """
    Returns a thumbnail path from a URL as a path relative to a storage location.

    For example:
        >>> _thumbnail_relative_to_location(
        >>>     "https://catalogue.dataspace.copernicus.eu/get-object?path=/Sentinel-1/SAR/EW_GRDM_1S/2025/08/07/S1A_EW_GRDM_1SDH_20250807T111242_20250807T111346_060429_078305_DB6A.SAFE/preview/thumbnail.png",
        >>>     "/eodata/Sentinel-1/SAR/EW_GRDM_1S/2025/08/07/S1A_EW_GRDM_1SDH_20250807T111242_20250807T111346_060429_078305_DB6A.SAFE"
        >>> )
        "preview/thumbnail.png"
    """

    url_path = thumbnail_url.split("?path=")[-1]
    url_path = url_path.removeprefix("/")
    location = location.removeprefix("/eodata/")
    return str(Path(url_path).relative_to(location))


@dataclass
class CopernicusStorageGranule:
    time: datetime
    granule_name: str
    location: str
    thumbnail: str | None = None

    @classmethod
    def from_data(cls, dataset: "xr.Dataset | CopernicusStorageGranule") -> "CopernicusStorageGranule":
        """Extract the granule information from a datapoint given as xarray dataset."""
        if isinstance(dataset, CopernicusStorageGranule):
            return dataset

        if "time" in dataset.dims:
            if dataset.sizes["time"] == 1:
                dataset = dataset.isel(time=0)
            else:
                raise ValueError("The given dataset has more than one granule.")

        time = datetime.combine(dataset.time.dt.date.item(), dataset.time.dt.time.item())

        location = dataset.location.item()

        thumbnail_path = None
        if "thumbnail" in dataset:
            thumbnail_path = dataset.thumbnail.item().strip()

        thumbnail = (
            _thumbnail_relative_to_eodata_location(thumbnail_path, location)
            if isinstance(thumbnail_path, str) and len(thumbnail_path) > 0
            else None
        )

        return cls(
            time,
            dataset.granule_name.item(),
            location,
            thumbnail,
        )


@dataclass
class USGSLandsatStorageGranule:
    time: datetime
    granule_name: str
    location: str
    thumbnail: str | None = None

    @classmethod
    def from_data(cls, dataset: "xr.Dataset | USGSLandsatStorageGranule") -> "USGSLandsatStorageGranule":
        """Extract the granule information from a datapoint given as xarray dataset."""
        if isinstance(dataset, USGSLandsatStorageGranule):
            return dataset

        if "time" in dataset.dims:
            if dataset.sizes["time"] == 1:
                dataset = dataset.isel(time=0)
            else:
                raise ValueError("The given dataset has more than one granule.")

        time = datetime.combine(dataset.time.dt.date.item(), dataset.time.dt.time.item())

        thumbnail_path: str | None = None
        if "thumbnail" in dataset:
            thumbnail_path = dataset.thumbnail.item()
        elif "overview" in dataset:
            thumbnail_path = dataset.overview.item()

        thumbnail = thumbnail_path.split("/")[-1] if isinstance(thumbnail_path, str) else None

        return cls(
            time,
            dataset.granule_name.item(),
            # Landsat 2 STAC items have an incorrect bucket name set, it should be usgs-landsat as well
            dataset.location.item().replace("s3://usgs-landsat-ard/", "s3://usgs-landsat/"),
            thumbnail,
        )
