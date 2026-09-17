from unittest.mock import patch

import pytest

from tilebox.workflows import Client


def test_http1_trusts_system_certificates() -> None:
    from pyqwest import HTTPVersion  # noqa: PLC0415

    with patch("pyqwest.SyncHTTPTransport") as transport, patch("tilebox.workflows.client.WorkflowTracer"):
        Client(url="https://api.tilebox.com", token="test-key", transport="http1")  # noqa: S106
        transport.assert_called_once_with(http_version=HTTPVersion.HTTP1, tls_include_system_certs=True)


@pytest.mark.parametrize(
    ("environment_url", "explicit_url", "expected_url"),
    [
        (None, None, "https://api.tilebox.com"),
        ("", None, "https://api.tilebox.com"),
        ("https://runner.example.com", None, "https://runner.example.com"),
        ("https://runner.example.com", "https://explicit.example.com", "https://explicit.example.com"),
        ("https://runner.example.com", "https://api.tilebox.com", "https://api.tilebox.com"),
    ],
)
def test_client_url_environment(
    monkeypatch: pytest.MonkeyPatch,
    environment_url: str | None,
    explicit_url: str | None,
    expected_url: str,
) -> None:
    monkeypatch.delenv("TILEBOX_API_URL", raising=False)
    if environment_url is not None:
        monkeypatch.setenv("TILEBOX_API_URL", environment_url)
    monkeypatch.setenv("TILEBOX_API_KEY", "runner-key")
    with (
        patch("tilebox.workflows.client.open_channel") as open_channel_mock,
        patch("tilebox.workflows.client.WorkflowTracer") as tracer_mock,
    ):
        client = Client() if explicit_url is None else Client(url=explicit_url)
        open_channel_mock.assert_called_once_with(expected_url, "runner-key")
        tracer_mock.assert_called_once_with(service=None, url=expected_url, token="runner-key")  # noqa: S106
        assert client._auth == {"url": expected_url, "token": "runner-key"}
