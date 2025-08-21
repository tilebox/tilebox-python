import numpy as np
import pytest
import xarray as xr
from hypothesis import given
from hypothesis.strategies import lists

from tests.storage_data import ers_granules, landsat_granules, s5p_granules, umbra_granules
from tilebox.storage.granule import (
    ASFStorageGranule,
    CopernicusStorageGranule,
    UmbraStorageGranule,
    USGSLandsatStorageGranule,
    _asf_download_urls,
)


def _asf_granule_to_datapoint(granule: ASFStorageGranule) -> xr.Dataset:
    datapoint = xr.Dataset()
    datapoint.coords["time"] = np.array(granule.time).astype("datetime64[ns]")
    datapoint["granule_name"] = granule.granule_name
    datapoint["file_size"] = granule.file_size
    datapoint["md5sum"] = granule.md5sum
    datapoint["quicklook_available"] = granule.urls.quicklook is not None
    return datapoint


@given(ers_granules())
def test_granule_from_asf_datapoint(granule: ASFStorageGranule) -> None:
    datapoint = _asf_granule_to_datapoint(granule)
    assert ASFStorageGranule.from_data(datapoint) == granule
    assert ASFStorageGranule.from_data(ASFStorageGranule.from_data(datapoint)) == granule


@given(lists(ers_granules(), min_size=2, max_size=5))
def test_granule_from_asf_datapoints(granules: list[ASFStorageGranule]) -> None:
    datapoints = [_asf_granule_to_datapoint(granule) for granule in granules]
    dataset = xr.concat(datapoints, dim="time")
    with pytest.raises(ValueError, match=".*more than one granule.*"):
        ASFStorageGranule.from_data(dataset)

    for i in range(len(granules)):  # converting a dataset with a time dimension of 1 should still work though
        assert ASFStorageGranule.from_data(dataset.isel(time=i)) == granules[i]


@given(ers_granules())
def test_ers_download_urls(granule: ASFStorageGranule) -> None:
    urls = _asf_download_urls(granule.granule_name)
    platform = granule.granule_name[:2]
    assert urls.quicklook is not None
    assert f"BROWSE/{platform}/{granule.granule_name}.jpg" in urls.quicklook

    assert f"L0/{platform}" in urls.data
    assert f"{granule.granule_name[:8]}" in urls.data
    assert "_STD_L0_" in urls.data
    assert f"{granule.granule_name[-4:]}" in urls.data


def _umbra_granule_to_datapoint(granule: UmbraStorageGranule) -> xr.Dataset:
    datapoint = xr.Dataset()
    datapoint.coords["time"] = np.array(granule.time).astype("datetime64[ns]")
    datapoint["granule_name"] = granule.granule_name
    datapoint["processing_level"] = granule.processing_level
    datapoint["location"] = granule.location
    return datapoint


@given(umbra_granules())
def test_granule_from_umbra_datapoint(granule: UmbraStorageGranule) -> None:
    datapoint = _umbra_granule_to_datapoint(granule)
    assert UmbraStorageGranule.from_data(datapoint) == granule
    assert UmbraStorageGranule.from_data(UmbraStorageGranule.from_data(datapoint)) == granule


@given(lists(umbra_granules(), min_size=2, max_size=5))
def test_granule_from_umbra_datapoints(granules: list[UmbraStorageGranule]) -> None:
    datapoints = [_umbra_granule_to_datapoint(granule) for granule in granules]
    dataset = xr.concat(datapoints, dim="time")
    with pytest.raises(ValueError, match=".*more than one granule.*"):
        UmbraStorageGranule.from_data(dataset)

    for i in range(len(granules)):  # converting a dataset with a time dimension of 1 should still work though
        assert UmbraStorageGranule.from_data(dataset.isel(time=i)) == granules[i]


def _copernicus_granule_to_datapoint(granule: CopernicusStorageGranule) -> xr.Dataset:
    datapoint = xr.Dataset()
    datapoint.coords["time"] = np.array(granule.time).astype("datetime64[ns]")
    datapoint["granule_name"] = granule.granule_name
    datapoint["location"] = granule.location
    datapoint["file_size"] = granule.file_size
    return datapoint


@given(s5p_granules())
def test_granule_from_copernicus_datapoint(granule: CopernicusStorageGranule) -> None:
    datapoint = _copernicus_granule_to_datapoint(granule)
    assert CopernicusStorageGranule.from_data(datapoint) == granule
    assert CopernicusStorageGranule.from_data(CopernicusStorageGranule.from_data(datapoint)) == granule


@given(lists(s5p_granules(), min_size=2, max_size=5))
def test_granule_from_copernicus_datapoints(granules: list[CopernicusStorageGranule]) -> None:
    datapoints = [_copernicus_granule_to_datapoint(granule) for granule in granules]
    dataset = xr.concat(datapoints, dim="time")
    with pytest.raises(ValueError, match=".*more than one granule.*"):
        CopernicusStorageGranule.from_data(dataset)

    for i in range(len(granules)):  # converting a dataset with a time dimension of 1 should still work though
        assert CopernicusStorageGranule.from_data(dataset.isel(time=i)) == granules[i]


def _landsat_granule_to_datapoint(granule: USGSLandsatStorageGranule) -> xr.Dataset:
    datapoint = xr.Dataset()
    datapoint.coords["time"] = np.array(granule.time).astype("datetime64[ns]")
    datapoint["granule_name"] = granule.granule_name
    datapoint["location"] = granule.location
    if granule.thumbnail is not None:
        datapoint["thumbnail"] = f"{granule.location}/{granule.thumbnail}"
    return datapoint


@given(landsat_granules())
def test_granule_from_landsat_datapoint(granule: USGSLandsatStorageGranule) -> None:
    datapoint = _landsat_granule_to_datapoint(granule)
    assert USGSLandsatStorageGranule.from_data(datapoint) == granule
    assert USGSLandsatStorageGranule.from_data(USGSLandsatStorageGranule.from_data(datapoint)) == granule


@given(lists(landsat_granules(), min_size=2, max_size=5))
def test_granule_from_landsat_datapoints(granules: list[USGSLandsatStorageGranule]) -> None:
    datapoints = [_landsat_granule_to_datapoint(granule) for granule in granules]
    dataset = xr.concat(datapoints, dim="time")
    with pytest.raises(ValueError, match=".*more than one granule.*"):
        USGSLandsatStorageGranule.from_data(dataset)

    for i in range(len(granules)):  # converting a dataset with a time dimension of 1 should still work though
        assert USGSLandsatStorageGranule.from_data(dataset.isel(time=i)) == granules[i]
