import os
import sys
from io import StringIO
from unittest.mock import patch

import pytest

from tilebox.datasets.aio.client import Client as AsyncClient
from tilebox.datasets.client import _log_server_message
from tilebox.datasets.data.datasets import ListDatasetsResponse
from tilebox.datasets.notices import print_notice
from tilebox.datasets.sync.client import Client


def test_print_notice_strips_markup_for_non_terminal_output(capsys: pytest.CaptureFixture[str]) -> None:
    print_notice("A [bold yellow]styled[/bold yellow] notice")

    assert capsys.readouterr() == ("", "A styled notice\n")


@pytest.mark.parametrize("terminal", [False, True])
def test_explicit_output_uses_its_own_terminal_status(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], terminal: bool
) -> None:
    output = StringIO()
    monkeypatch.setattr(output, "isatty", lambda: terminal)
    monkeypatch.setattr(sys.stderr, "isatty", lambda: not terminal)
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("TERM", "xterm")

    print_notice("[red]notice[/red]", output=output)

    assert output.getvalue() == ("\033[0m\033[31mnotice\033[0m\n" if terminal else "notice\n")
    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        (
            "[red]red [bold]bold[/bold] red[/red] plain",
            "\033[0m\033[31mred \033[0m\033[31;1mbold\033[0m\033[31m red\033[0m plain\n",
        ),
        ("[bold blue]blue[/bold blue]", "\033[0m\033[1;34mblue\033[0m\n"),
        (
            "[green]green [red]red[/red] green[/green]",
            "\033[0m\033[32mgreen \033[0m\033[32;31mred\033[0m\033[32m green\033[0m\n",
        ),
        ("[cyan]unclosed", "\033[0m\033[36munclosed\033[0m\n"),
        ("[unknown]literal[/unknown] [/red]", "[unknown]literal[/unknown] [/red]\n"),
    ],
)
def test_terminal_styles(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], message: str, expected: str
) -> None:
    monkeypatch.setattr(sys.stderr, "isatty", lambda: True)
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("TERM", "xterm")
    print_notice(message)
    assert capsys.readouterr() == ("", expected)


@pytest.mark.parametrize(("variable", "value"), [("NO_COLOR", ""), ("NO_COLOR", "1"), ("TERM", "dumb")])
def test_terminal_color_opt_out(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], variable: str, value: str
) -> None:
    monkeypatch.setattr(sys.stderr, "isatty", lambda: True)
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("TERM", "xterm")
    monkeypatch.setenv(variable, value)
    print_notice("[yellow]normal [bold]bold[/bold] normal[/yellow]")
    assert capsys.readouterr() == ("", "normal bold normal\n")


@pytest.mark.parametrize("client_type", [Client, AsyncClient])
@patch.dict(os.environ, {}, clear=True)
def test_anonymous_notice_can_be_disabled(
    capsys: pytest.CaptureFixture[str], client_type: type[Client] | type[AsyncClient]
) -> None:
    with patch(f"{client_type.__module__}.open_channel"):
        client_type(warn_if_unauthenticated=False)

    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize("client_type", [Client, AsyncClient])
@patch.dict(os.environ, {}, clear=True)
def test_anonymous_notice_is_printed(
    capsys: pytest.CaptureFixture[str], client_type: type[Client] | type[AsyncClient]
) -> None:
    with patch(f"{client_type.__module__}.open_channel"):
        client_type()

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Using anonymous open data access" in captured.err


def test_server_message_is_printed(capsys: pytest.CaptureFixture[str]) -> None:
    response = ListDatasetsResponse([], [], "A message from the server")

    assert _log_server_message(response) is response
    assert capsys.readouterr() == ("", "A message from the server\n\n")
