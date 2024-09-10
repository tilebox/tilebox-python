import pytest
from httpx import AsyncClient, BasicAuth
from hypothesis import given
from pytest_httpx import HTTPXMock

from tests.storage_data import ers_granules, s1_granules
from tilebox.storage.granule import ASFStorageGranule
from tilebox.storage.providers import _asf_login, download_urls


@given(ers_granules())
def test_ers_download_urls(granule: ASFStorageGranule) -> None:
    urls = download_urls(granule.storage_provider, granule.granule_name, granule.processing_level)
    platform = granule.granule_name[:2]
    assert urls.quicklook is not None
    assert f"BROWSE/{platform}/{granule.granule_name}.jpg" in urls.quicklook

    assert f"{granule.processing_level}/{platform}" in urls.data
    assert f"{granule.granule_name[:8]}" in urls.data
    assert f"_STD_{granule.processing_level}_" in urls.data
    assert f"{granule.granule_name[-4:]}" in urls.data


@given(s1_granules())
def test_sentinel1_download_urls(granule: ASFStorageGranule) -> None:
    urls = download_urls(granule.storage_provider, granule.granule_name, granule.processing_level)
    platform = granule.granule_name[0] + granule.granule_name[2]
    assert urls.quicklook is None
    assert f"RAW/{platform}/{granule.granule_name}.zip" in urls.data


@pytest.mark.anyio
async def test_asf_login(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(headers={"Set-Cookie": "logged_in=yes"})

    client = await _asf_login(("username", "password"))
    assert isinstance(client, AsyncClient)
    assert "asf_search" in client.headers["Client-Id"]
    assert isinstance(client.auth, BasicAuth)
    assert client.cookies["logged_in"] == "yes"


@pytest.mark.anyio
async def test_asf_login_invalid_auth(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(401)
    with pytest.raises(ValueError, match="Invalid username or password."):
        await _asf_login(("username", "password"))
