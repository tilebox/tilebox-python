from unittest.mock import patch

import pytest

from tilebox.workflows import Client


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
        patch("tilebox.workflows.client._create_tilebox_logger_provider") as logger_provider_mock,
        patch("tilebox.workflows.client.WorkflowTracer") as tracer_mock,
    ):
        client = Client() if explicit_url is None else Client(url=explicit_url)
        open_channel_mock.assert_called_once_with(expected_url, "runner-key")
        logger_provider_mock.assert_called_once_with(service=None, url=expected_url, token="runner-key")  # noqa: S106
        tracer_mock.assert_called_once_with(service=None, url=expected_url, token="runner-key")  # noqa: S106
        assert client._auth == {"url": expected_url, "token": "runner-key"}
