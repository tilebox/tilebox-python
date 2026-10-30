from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest
from pyqwest import Client, FullResponse

from tilebox.storage.providers import _asf_login

ASF_LOGIN_URL = "https://urs.earthdata.nasa.gov/oauth/authorize"


@pytest.fixture
def asf_server(monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[str, list[dict[str, Any]]]]:
    requests: list[dict[str, Any]] = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            requests.append({"path": self.path, "headers": self.headers})
            if self.path.startswith("/oauth/authorize"):
                self.send_response(302)
                # A different host exercises credential stripping on redirects.
                self.send_header("Location", f"http://localhost:{server.server_port}/login")
            elif self.path == "/login":
                self.send_response(200)
                self.send_header("Set-Cookie", "logged_in=yes; Path=/")
            else:
                self.send_response(200 if self.headers.get("Cookie") == "logged_in=yes" else 403)
            self.send_header("Content-Length", "4")
            self.end_headers()
            self.wfile.write(b"data")

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    original_get = Client.get

    async def local_login(client: Client, url: str, **kwargs: Any) -> FullResponse:
        if url == ASF_LOGIN_URL:
            url = f"http://127.0.0.1:{server.server_port}/oauth/authorize"
        return await original_get(client, url, **kwargs)

    monkeypatch.setattr(Client, "get", local_login)
    try:
        yield f"http://localhost:{server.server_port}", requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


@pytest.mark.asyncio
async def test_asf_login(asf_server: tuple[str, list[dict[str, Any]]]) -> None:
    origin, requests = asf_server
    async with await _asf_login(("username", "password")) as transport:
        client = Client(transport)
        response = await client.get(f"{origin}/quicklook")
        assert response.status == 200
        assert response.content == b"data"
        async with client.stream("GET", f"{origin}/download") as response:
            assert response.status == 200
            assert b"".join([bytes(chunk) async for chunk in response.content]) == b"data"

    assert "asf_search" in requests[0]["headers"]["Client-Id"]
    assert parse_qs(urlsplit(requests[0]["path"]).query) == {
        "client_id": ["BO_n7nTIlMljdvU6kRRB3g"],
        "response_type": ["code"],
        "redirect_uri": ["https://auth.asf.alaska.edu/login"],
    }
    assert all(request["headers"].get("Authorization") is None for request in requests[1:])
    assert all(request["headers"]["Cookie"] == "logged_in=yes" for request in requests[2:])


@pytest.mark.asyncio
@pytest.mark.parametrize(("status", "message"), [(401, "Invalid username or password"), (503, "HTTP 503")])
async def test_asf_login_failure(http_responses: dict[str, tuple[int, bytes]], status: int, message: str) -> None:
    http_responses[ASF_LOGIN_URL] = (status, b"secret")
    with pytest.raises(ValueError, match=message) as error:
        await _asf_login(("username", "password"))
    assert "secret" not in str(error.value)
