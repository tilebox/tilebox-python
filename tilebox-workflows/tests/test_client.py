from pathlib import Path
from unittest.mock import patch
from uuid import UUID

import pytest

from _tilebox.errors import NotFoundError
from _tilebox.replay import Replay
from tilebox.workflows import Client


def test_client_closes_connection() -> None:
    with patch("tilebox.workflows.client.Connection") as connection, patch("tilebox.workflows.client.WorkflowTracer"):
        with Client(url="https://api.tilebox.com", token="test-key"):  # noqa: S106
            connection.return_value.close.assert_not_called()
        connection.return_value.close.assert_called_once()


@pytest.mark.parametrize(
    ("client_name", "rpc_method", "identifier"),
    [
        ("jobs", "/workflows.v1.JobService/GetJob", UUID(int=1)),
        ("clusters", "/workflows.v1.WorkflowsService/GetCluster", "missing"),
        ("workflows", "/workflows.v1.WorkflowsService/GetWorkflow", "missing"),
        ("automations", "/workflows.v1.AutomationService/GetAutomation", UUID(int=1)),
        ("storage_locations", "/workflows.v1.StorageLocationService/GetStorageLocation", UUID(int=1)),
    ],
)
def test_public_clients_translate_connect_errors(
    tmp_path: Path, client_name: str, rpc_method: str, identifier: UUID | str
) -> None:
    """Propagate replayed Connect failures through the shared connection as public errors."""
    recording = tmp_path / "not-found.rpcs.bin"
    recording.write_text(f"{rpc_method}\n\n5\nResource not found\n")
    with (
        patch("tilebox.workflows.client.WorkflowTracer"),
        Client(
            url="https://api.tilebox.com",
            token="test-key",  # noqa: S106
            interceptors=[Replay(recording, assert_request_matches=False)],
        ) as client,
        pytest.raises(NotFoundError, match="Resource not found"),
    ):
        getattr(client, client_name)().find(identifier)


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
        patch("tilebox.workflows.client.Connection") as connection_mock,
        patch("tilebox.workflows.client.WorkflowTracer") as tracer_mock,
    ):
        client = Client() if explicit_url is None else Client(url=explicit_url)
        connection_mock.assert_called_once_with(expected_url, "runner-key", transport="http2", interceptors=())
        tracer_mock.assert_called_once_with(service=None, url=expected_url, token="runner-key")  # noqa: S106
        assert client._auth == {"url": expected_url, "token": "runner-key"}
