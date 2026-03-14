"""Tests for tilebox_publish_discover module."""

import json
import subprocess
import sys
from pathlib import Path

import pytest
import tilebox_publish_discover.discover as discover_module
from tilebox_publish_discover.discover import (
    CODE_DISCOVERY_PROCESS_FAILED,
    CODE_NO_TASKS_DISCOVERED,
    CODE_TASK_IDENTIFIER_DUPLICATE,
    CODE_TASK_IDENTIFIER_INVALID,
    DISCOVERY_KIND_PYTHON_EXPLICIT,
    DISCOVERY_PROTOCOL,
    RUNTIME_KIND_PYTHON_UV,
    DiscoveredTask,
    DiscoveryError,
    _extract_task_info,
    _parse_entrypoint,
    discover,
)

from tilebox.workflows.task import ExecutionContext, Task

_WORKFLOWS_ROOT = str(Path(__file__).parent.parent)


class SimpleTask(Task):
    def execute(self, context: ExecutionContext) -> None:
        pass


class VersionedTask(Task):
    @staticmethod
    def identifier() -> tuple[str, str]:
        return "tilebox.tests.VersionedTask", "v2.5"

    def execute(self, context: ExecutionContext) -> None:
        pass


class AnotherTask(Task):
    @staticmethod
    def identifier() -> tuple[str, str]:
        return "tilebox.tests.AnotherTask", "v1.0"

    def execute(self, context: ExecutionContext) -> None:
        pass


class DuplicateTaskA(Task):
    @staticmethod
    def identifier() -> tuple[str, str]:
        return "tilebox.tests.Duplicate", "v1.2"

    def execute(self, context: ExecutionContext) -> None:
        pass


class DuplicateTaskB(Task):
    @staticmethod
    def identifier() -> tuple[str, str]:
        return "tilebox.tests.Duplicate", "v1.2"

    def execute(self, context: ExecutionContext) -> None:
        pass


class NoisyIdentifierTask(Task):
    @staticmethod
    def identifier() -> tuple[str, str]:
        sys.stdout.write("noise from identifier\n")
        return "tilebox.tests.Noisy", "v3.0"

    def execute(self, context: ExecutionContext) -> None:
        pass


class NotATask:
    pass


def _run_discovery_subprocess(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        [
            sys.executable,
            "-m",
            "tilebox_publish_discover",
            *args,
        ],
        capture_output=True,
        text=True,
        check=False,
        cwd=_WORKFLOWS_ROOT,
    )


def test_parse_entrypoint_valid() -> None:
    assert _parse_entrypoint("workflow:Task") == ("workflow", "Task")


def test_parse_entrypoint_invalid() -> None:
    with pytest.raises(DiscoveryError, match="Invalid task reference format"):
        _parse_entrypoint("workflow_task")


def test_extract_task_info_default_identifier() -> None:
    result = _extract_task_info(SimpleTask, "tests.test_publish_discover:SimpleTask")
    assert result == DiscoveredTask(
        name="SimpleTask",
        version="v0.0",
        display="SimpleTask",
        source_ref="tests.test_publish_discover:SimpleTask",
    )


def test_extract_task_info_custom_identifier() -> None:
    result = _extract_task_info(VersionedTask, "tests.test_publish_discover:VersionedTask")
    assert result == DiscoveredTask(
        name="tilebox.tests.VersionedTask",
        version="v2.5",
        display="VersionedTask",
        source_ref="tests.test_publish_discover:VersionedTask",
    )


def test_extract_task_info_invalid_identifier(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise_invalid_identifier(_task_class: type | Task) -> object:
        raise ValueError("Invalid version string: 1.2")

    monkeypatch.setattr(discover_module.TaskMeta, "for_task", staticmethod(_raise_invalid_identifier))

    with pytest.raises(DiscoveryError, match="Invalid version string") as exc_info:
        _extract_task_info(SimpleTask, "tests.test_publish_discover:SimpleTask")

    assert exc_info.value.code == CODE_TASK_IDENTIFIER_INVALID


def test_discover_explicit_tasks_success_and_sorted() -> None:
    tasks = discover(
        discovery_kind=DISCOVERY_KIND_PYTHON_EXPLICIT,
        explicit_tasks=[
            "tests.test_publish_discover:VersionedTask",
            "tests.test_publish_discover:AnotherTask",
        ],
    )

    assert len(tasks) == 2
    assert tasks[0].name == "tilebox.tests.AnotherTask"
    assert tasks[1].name == "tilebox.tests.VersionedTask"


def test_discover_explicit_tasks_missing_refs() -> None:
    with pytest.raises(DiscoveryError, match="No tasks discovered") as exc_info:
        discover(discovery_kind=DISCOVERY_KIND_PYTHON_EXPLICIT, explicit_tasks=None)

    assert exc_info.value.code == CODE_NO_TASKS_DISCOVERED


def test_discover_explicit_tasks_invalid_ref() -> None:
    with pytest.raises(DiscoveryError, match="Invalid task reference format") as exc_info:
        discover(
            discovery_kind=DISCOVERY_KIND_PYTHON_EXPLICIT,
            explicit_tasks=["tests.test_publish_discover"],
        )

    assert exc_info.value.code == CODE_DISCOVERY_PROCESS_FAILED


def test_discover_explicit_tasks_non_task() -> None:
    with pytest.raises(DiscoveryError, match="does not resolve to a Task subclass") as exc_info:
        discover(
            discovery_kind=DISCOVERY_KIND_PYTHON_EXPLICIT,
            explicit_tasks=["tests.test_publish_discover:NotATask"],
        )

    assert exc_info.value.code == CODE_DISCOVERY_PROCESS_FAILED


def test_discover_explicit_tasks_duplicate_identifier() -> None:
    with pytest.raises(DiscoveryError, match="Duplicate task identifier discovered") as exc_info:
        discover(
            discovery_kind=DISCOVERY_KIND_PYTHON_EXPLICIT,
            explicit_tasks=[
                "tests.test_publish_discover:DuplicateTaskA",
                "tests.test_publish_discover:DuplicateTaskB",
            ],
        )

    assert exc_info.value.code == CODE_TASK_IDENTIFIER_DUPLICATE


def test_discover_rejects_unknown_discovery_kind() -> None:
    with pytest.raises(DiscoveryError, match="Unsupported discovery kind") as exc_info:
        discover(discovery_kind="registry_function", explicit_tasks=["tests.test_publish_discover:VersionedTask"])

    assert exc_info.value.code == CODE_DISCOVERY_PROCESS_FAILED


def test_main_subprocess_success() -> None:
    result = _run_discovery_subprocess(
        "--discovery-kind",
        DISCOVERY_KIND_PYTHON_EXPLICIT,
        "--task",
        "tests.test_publish_discover:VersionedTask",
        "--task",
        "tests.test_publish_discover:AnotherTask",
    )

    assert result.returncode == 0, f"stderr: {result.stderr}"
    payload = json.loads(result.stdout)

    assert payload["ok"] is True
    assert payload["protocol"] == DISCOVERY_PROTOCOL
    assert payload["runtime_kind"] == RUNTIME_KIND_PYTHON_UV
    assert payload["discovery_kind"] == DISCOVERY_KIND_PYTHON_EXPLICIT
    assert payload["tasks"][0]["name"] == "tilebox.tests.AnotherTask"
    assert payload["tasks"][1]["name"] == "tilebox.tests.VersionedTask"
    assert payload["warnings"] == []


def test_main_subprocess_failure_no_tasks() -> None:
    result = _run_discovery_subprocess("--discovery-kind", DISCOVERY_KIND_PYTHON_EXPLICIT)

    assert result.returncode == 2
    payload = json.loads(result.stdout)

    assert payload["ok"] is False
    assert payload["code"] == CODE_NO_TASKS_DISCOVERED


def test_main_subprocess_failure_unknown_discovery_kind() -> None:
    result = _run_discovery_subprocess(
        "--discovery-kind",
        "registry_function",
        "--task",
        "tests.test_publish_discover:VersionedTask",
    )

    assert result.returncode == 2
    payload = json.loads(result.stdout)

    assert payload["ok"] is False
    assert payload["code"] == CODE_DISCOVERY_PROCESS_FAILED


def test_main_subprocess_user_stdout_goes_to_stderr() -> None:
    result = _run_discovery_subprocess(
        "--discovery-kind",
        DISCOVERY_KIND_PYTHON_EXPLICIT,
        "--task",
        "tests.test_publish_discover:NoisyIdentifierTask",
    )

    assert result.returncode == 0, f"stderr: {result.stderr}"
    payload = json.loads(result.stdout)

    assert payload["ok"] is True
    assert "noise from identifier" not in result.stdout
    assert "noise from identifier" in result.stderr
