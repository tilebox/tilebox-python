import pytest
from pyqwest import Client, Request, Response, Transport


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def http_requests() -> list[Request]:
    return []


@pytest.fixture
def http_responses(monkeypatch: pytest.MonkeyPatch, http_requests: list[Request]) -> dict[str, tuple[int, bytes]]:
    responses = {"https://urs.earthdata.nasa.gov/oauth/authorize": (200, b"")}

    class MockTransport:
        async def execute(self, request: Request) -> Response:
            http_requests.append(request)
            assert request.method == "GET"
            status, body = responses[request.url.split("?", 1)[0]]
            return Response(status=status, content=body)

    original_init = Client.__init__

    def init(client: Client, _transport: Transport | None = None) -> None:
        original_init(client, MockTransport())

    monkeypatch.setattr(Client, "__init__", init)
    return responses
