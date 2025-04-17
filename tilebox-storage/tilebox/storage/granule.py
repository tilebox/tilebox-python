from dataclasses import dataclass
from datetime import datetime

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
    processing_level: str
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
            dataset.processing_level.item(),
            dataset.location.item(),
        )


@dataclass
class CopernicusStorageGranule:
    time: datetime
    granule_name: str
    location: str
    file_size: int

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

        return cls(
            time,
            dataset.granule_name.item(),
            dataset.location.item(),
            dataset.file_size.item(),
        )
