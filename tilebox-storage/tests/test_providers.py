import re
from typing import cast

import pytest
import responses
from niquests import AsyncSession
from niquests.cookies import RequestsCookieJar

from tilebox.storage.providers import _asf_login

pytestmark = pytest.mark.usefixtures("responses_mock")

ASF_LOGIN_URL = "https://urs.earthdata.nasa.gov/oauth/authorize"


@pytest.mark.asyncio
async def test_asf_login() -> None:
    responses.add(responses.GET, ASF_LOGIN_URL, headers={"Set-Cookie": "logged_in=yes"})

    client = await _asf_login(("username", "password"))
    cookies = cast(RequestsCookieJar, client.cookies)

    assert isinstance(client, AsyncSession)
    assert "asf_search" in str(client.headers["Client-Id"])
    assert client.auth == ("username", "password")
    assert cookies["logged_in"] == "yes"

    await client.close()


@pytest.mark.asyncio
async def test_asf_login_invalid_auth() -> None:
    responses.add(responses.GET, ASF_LOGIN_URL, status=401)

    with pytest.raises(ValueError, match=re.escape("Invalid username or password.")):
        await _asf_login(("username", "password"))
