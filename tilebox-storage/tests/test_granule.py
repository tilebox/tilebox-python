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
    _thumbnail_relative_to_eodata_location,
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


@pytest.mark.parametrize(
    ("thumbnail_url", "location", "expected"),
    [
        (
            "https://catalogue.dataspace.copernicus.eu/get-object?path=/Sentinel-1/SAR/EW_GRDM_1S/2025/08/07/S1A_EW_GRDM_1SDH_20250807T111242_20250807T111346_060429_078305_DB6A.SAFE/preview/thumbnail.png",
            "/eodata/Sentinel-1/SAR/EW_GRDM_1S/2025/08/07/S1A_EW_GRDM_1SDH_20250807T111242_20250807T111346_060429_078305_DB6A.SAFE",
            "preview/thumbnail.png",
        ),
        (
            "https://catalogue.dataspace.copernicus.eu/get-object?path=/Sentinel-2/MSI/L1C/2025/08/07/S2B_MSIL1C_20250807T004159_N0511_R045_T08XNR_20250807T004945.SAFE/S2B_MSIL1C_20250807T004159_N0511_R045_T08XNR_20250807T004945-ql.jpg",
            "/eodata/Sentinel-2/MSI/L1C/2025/08/07/S2B_MSIL1C_20250807T004159_N0511_R045_T08XNR_20250807T004945.SAFE",
            "S2B_MSIL1C_20250807T004159_N0511_R045_T08XNR_20250807T004945-ql.jpg",
        ),
        (
            "https://catalogue.dataspace.copernicus.eu/get-object?path=/Sentinel-3/OLCI/OL_2_LFR___/2025/08/07/S3A_OL_2_LFR____20250807T011653_20250807T011953_20250807T033036_0179_129_074_1620_PS1_O_NR_003.SEN3/quicklook.jpg",
            "/eodata/Sentinel-3/OLCI/OL_2_LFR___/2025/08/07/S3A_OL_2_LFR____20250807T011653_20250807T011953_20250807T033036_0179_129_074_1620_PS1_O_NR_003.SEN3",
            "quicklook.jpg",
        ),
        (
            "https://catalogue.dataspace.copernicus.eu/get-object?path=/Sentinel-3/SLSTR/SL_1_RBT___/2025/08/07/S3B_SL_1_RBT____20250807T002314_20250807T002614_20250807T025411_0179_109_316_0720_ESA_O_NR_004.SEN3/quicklook.jpg",
            "/eodata/Sentinel-3/SLSTR/SL_1_RBT___/2025/08/07/S3B_SL_1_RBT____20250807T002314_20250807T002614_20250807T025411_0179_109_316_0720_ESA_O_NR_004.SEN3",
            "quicklook.jpg",
        ),
        (
            "https://catalogue.dataspace.copernicus.eu/get-object?path=/Sentinel-3/SYNERGY/SY_2_VG1___/2025/08/04/S3A_SY_2_VG1____20250804T000000_20250804T235959_20250806T202029_AUSTRALASIA_______PS1_O_NT_002.SEN3/quicklook.jpg",
            "/eodata/Sentinel-3/SYNERGY/SY_2_VG1___/2025/08/04/S3A_SY_2_VG1____20250804T000000_20250804T235959_20250806T202029_AUSTRALASIA_______PS1_O_NT_002.SEN3",
            "quicklook.jpg",
        ),
    ],
)
def test_thumbnail_relative_to_eodata_location(thumbnail_url: str, location: str, expected: str) -> None:
    assert (
        _thumbnail_relative_to_eodata_location(
            thumbnail_url,
            location,
        )
        == expected
    )


def _copernicus_granule_to_datapoint(granule: CopernicusStorageGranule) -> xr.Dataset:
    datapoint = xr.Dataset()
    datapoint.coords["time"] = np.array(granule.time).astype("datetime64[ns]")
    datapoint["granule_name"] = granule.granule_name
    datapoint["location"] = granule.location
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
