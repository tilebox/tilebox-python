import os
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest
import xarray as xr
from shapely import Polygon

from _tilebox.grpc.error import NotFoundError
from _tilebox.grpc.replay import open_recording_channel, open_replay_channel
from tilebox.datasets import Client, TimeseriesDataset
from tilebox.datasets.data.datapoint import DatapointPage
from tilebox.datasets.data.time_interval import us_to_datetime


def replay_client(replay_file: str, assert_request_matches: bool = True) -> Client:
    replay = Path(__file__).parent / "testdata" / "recordings" / replay_file
    replay_channel = open_replay_channel(replay, assert_request_matches)

    with patch("tilebox.datasets.sync.client.open_channel") as open_channel_mock:
        open_channel_mock.return_value = replay_channel
        # url/token doesn't matter since its a mocked channel
        client = Client(
            url="https://api.tilebox.com",
            token="token",  # noqa: S106
        )
        open_channel_mock.assert_called_once()

    return client


def record_client(recording_file: str) -> Client:
    recording = Path(__file__).parent / "testdata" / "recordings" / recording_file
    # this will open a channel to api.tilebox.com, which will send real requests to the server, and record them
    # for later offline replay
    recording_channel = open_recording_channel(
        "https://api.tilebox.com", os.environ["TILEBOX_OPENDATA_ONLY_API_KEY"], recording
    )

    with patch("tilebox.datasets.sync.client.open_channel") as open_channel_mock:
        open_channel_mock.return_value = recording_channel
        # url/token doesn't matter since its a mocked channel
        client = Client(url="https://api.tilebox.com", token="token")  # noqa: S106
        open_channel_mock.assert_called_once()

    return client


def test_list_datasets() -> None:
    # we send our package version as client_info, so the outgoing request changes over time, so let's not check it
    client = replay_client("list_datasets.rpcs.bin", assert_request_matches=False)

    datasets = client.datasets()
    # let's check that we can access a dataset
    assert isinstance(datasets.open_data.copernicus.sentinel2_msi, TimeseriesDataset)
    # let's check that the repr contains the summaries of the datasets
    assert "sentinel2_msi" in repr(datasets)
    assert "Sentinel-2 is equipped with an optical instrument payload that samples" in repr(datasets)


def test_list_collections() -> None:
    client = replay_client("list_s2_collections.rpcs.bin")

    s2_dataset = client.dataset("0190bbe6-1215-a90d-e8ce-0086add856c2")
    collections = s2_dataset.collections(availability=True, count=False)
    assert sorted(collections) == ["S2A_S2MSI1C", "S2A_S2MSI2A", "S2B_S2MSI1C", "S2B_S2MSI2A"]


def test_collection_info() -> None:
    client = replay_client("s2_collection_info.rpcs.bin")

    s2_dataset = client.dataset("0190bbe6-1215-a90d-e8ce-0086add856c2")
    collections = s2_dataset.collections(availability=False, count=False)

    for collection_name in ["S2A_S2MSI1C", "S2A_S2MSI2A"]:
        collection = collections[collection_name]
        info = collection.info(availability=True, count=False)
        assert "Collection S2A_S2MSI" in repr(info)
        assert "[2015-07-04T10:10:06.027 UTC, " in repr(info)


def test_dataset_not_found() -> None:
    client = replay_client("list_dataset_not_found.rpcs.bin")

    with pytest.raises(NotFoundError, match="no such dataset"):
        client.dataset("94e06073-ea61-40a2-a61c-446871d47932")


def test_find_datapoint() -> None:
    client = replay_client("find_s2_datapoint.rpcs.bin")

    s2_dataset = client.dataset("0190bbe6-1215-a90d-e8ce-0086add856c2")
    collection = s2_dataset.collection("S2A_S2MSI1C")

    for skip_data in (False, True):
        datapoint = collection.find("0181f4ef-2040-1613-3eed-1c970dde6d2b", skip_data=skip_data)
        assert isinstance(datapoint, xr.Dataset)

        assert datapoint.id.item() == "0181f4ef-2040-1613-3eed-1c970dde6d2b"
        assert _dt(datapoint.time.item()) == datetime(2022, 7, 13, 0, 22, 1, 24000, tzinfo=timezone.utc)
        assert _dt(datapoint.ingestion_time.item()) == datetime(2024, 7, 17, 4, 14, 29, 349263, tzinfo=timezone.utc)

        if not skip_data:
            assert datapoint.granule_name.item() == "S2A_MSIL1C_20220713T002201_N0400_R102_T08XNS_20220713T015332.SAFE"
            assert datapoint.processing_level.item() == "L1C"
            assert datapoint.copernicus_id.item() == "65505f82-76dd-5e85-b947-a6c879e07446"
            assert isinstance(datapoint.geometry.item(), Polygon)
        else:
            assert "granule_name" not in datapoint
            assert "processing_level" not in datapoint
            assert "copernicus_id" not in datapoint
            assert "geometry" not in datapoint


def test_datapoint_not_found() -> None:
    client = replay_client("s2_datapoint_not_found.rpcs.bin")

    s2_dataset = client.dataset("0190bbe6-1215-a90d-e8ce-0086add856c2")
    collection = s2_dataset.collection("S2A_S2MSI1C")

    with pytest.raises(NotFoundError, match="No such datapoint.*"):
        collection.find("0181f4dc-53c0-4912-acda-e35a368994fc")  # is in another collection


def test_load_data() -> None:
    client = replay_client("load_s2_data_interval.rpcs.bin")

    s2_dataset = client.dataset("0190bbe6-1215-a90d-e8ce-0086add856c2")
    collection = s2_dataset.collection("S2A_S2MSI1C")

    for skip_data in (False, True):
        data = collection.load(("2022-07-13", "2022-07-13T02:00"), skip_data=skip_data)
        assert isinstance(data, xr.Dataset)

        assert data.sizes["time"] == 378
        assert data.id[0] == "0181f4ef-2040-0566-def5-50246aabcabc"
        assert data.id[-1] == "0181f506-51c0-ffb7-20cb-a2ab4f5057cf"

        if not skip_data:
            assert data.granule_name[0] == "S2A_MSIL1C_20220713T002201_N0400_R102_T09XWK_20220713T015332.SAFE"
            assert data.granule_name[-1] == "S2A_MSIL1C_20220713T004721_N0400_R102_T53HNA_20220713T021615.SAFE"
        else:
            assert "granule_name" not in data


def test_load_data_pagination() -> None:
    client = replay_client("load_s2_data_interval_paging.rpcs.bin")

    s2_dataset = client.dataset("0190bbe6-1215-a90d-e8ce-0086add856c2")
    collection = s2_dataset.collection("S2A_S2MSI1C")

    pages = list(collection._iter_pages(("2022-07-13", "2022-07-13T02:00"), page_size=10))

    assert len(pages) == 38  # we have 378 datapoints, so 38 pages, and the last page has only 8 datapoints

    for i, page in enumerate(pages):
        assert isinstance(page, DatapointPage)
        assert page.meta[0].id >= "0181f4ef-2040-0566-def5-50246aabcabc"
        assert page.meta[-1].id <= "0181f506-51c0-ffb7-20cb-a2ab4f5057cf"
        is_last_page = i == len(pages) - 1
        expected_len = 8 if is_last_page else 10
        assert len(page.meta) == expected_len


def _dt(timestamp_nano: int) -> datetime:
    return us_to_datetime(timestamp_nano // 1000)
