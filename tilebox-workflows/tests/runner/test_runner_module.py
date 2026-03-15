import json

import pytest

from tilebox.workflows import ExecutionContext, Task
from tilebox.workflows import runner


class DiscoveryTaskB(Task):
    def execute(self, context: ExecutionContext) -> None:
        _ = context


class DiscoveryTaskA(Task):
    def execute(self, context: ExecutionContext) -> None:
        _ = context


@pytest.fixture(autouse=True)
def reset_runner_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runner, "_REGISTERED_TASKS", {})


def test_runner_discovery_payload_is_runtime_command_compatible(capsys: pytest.CaptureFixture[str]) -> None:
    runner.register(DiscoveryTaskB)
    runner.register(DiscoveryTaskA)

    exit_code = runner.main(["--tilebox-discover"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["protocol"] == "tilebox.discovery.v1"
    assert payload["runtime_kind"] == "python_uv"
    assert payload["discovery_kind"] == "runtime_command"
    assert payload["warnings"] == []
    assert [task["name"] for task in payload["tasks"]] == ["DiscoveryTaskA", "DiscoveryTaskB"]


def test_runner_discovery_fails_without_registered_tasks(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = runner.main(["--tilebox-discover"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 1
    assert payload["ok"] is False
    assert payload["code"] == "TBX-PUB-012"


def test_runner_register_rejects_duplicates() -> None:
    runner.register(DiscoveryTaskA)
    with pytest.raises(ValueError, match="Duplicate task identifier"):
        runner.register(DiscoveryTaskA)
