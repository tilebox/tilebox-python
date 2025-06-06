from dataclasses import dataclass
from datetime import datetime

import xarray as xr

from tilebox.storage.providers import StorageURLs, download_urls


@dataclass
class ASFStorageGranule:
    time: datetime
    granule_name: str
    processing_level: str
    storage_provider: str
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
        processing_level = dataset.processing_level.item()
        storage_provider = dataset.storage_provider.item()
        quicklook_available = "quicklook_available" in dataset and dataset.quicklook_available.item()

        urls = download_urls(storage_provider, granule_name, processing_level)

        if not quicklook_available and urls.quicklook is not None:
            urls = StorageURLs(urls.data, None)

        time = datetime.combine(dataset.time.dt.date.item(), dataset.time.dt.time.item())

        return cls(
            time,
            granule_name,
            processing_level,
            storage_provider,
            dataset.file_size.item(),
            dataset.md5sum.item(),
            urls,
        )


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
