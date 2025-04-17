import pytest
from httpx import AsyncClient, BasicAuth
from pytest_httpx import HTTPXMock

from tilebox.storage.providers import _asf_login


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
