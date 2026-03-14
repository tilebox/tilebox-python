"""Core discovery logic for extracting task identifiers from a Python project."""

from __future__ import annotations

import argparse
import contextlib
import importlib
import json
import sys
from dataclasses import asdict, dataclass
from typing import Any

from tilebox.workflows.task import Task, TaskMeta

DISCOVERY_PROTOCOL = "tilebox.discovery.v1"
RUNTIME_KIND_PYTHON_UV = "python_uv"
DISCOVERY_KIND_PYTHON_EXPLICIT = "python_explicit"

CODE_DISCOVERY_PROCESS_FAILED = "TBX-PUB-010"
CODE_NO_TASKS_DISCOVERED = "TBX-PUB-012"
CODE_TASK_IDENTIFIER_INVALID = "TBX-PUB-013"
CODE_TASK_IDENTIFIER_DUPLICATE = "TBX-PUB-014"


class DiscoveryError(Exception):
    """A structured discovery error aligned with blueprint codes."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        hint: str | None = None,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.hint = hint
        self.details = details or {}


@dataclass(frozen=True)
class DiscoveredTask:
    """A discovered task identifier ready for JSON serialization."""

    name: str
    version: str
    display: str
    source_ref: str


def _parse_entrypoint(entrypoint: str) -> tuple[str, str]:
    if ":" not in entrypoint:
        raise DiscoveryError(
            code=CODE_DISCOVERY_PROCESS_FAILED,
            message=(
                f"Invalid task reference format: '{entrypoint}'. "
                "Expected 'module:TaskClass' for python_explicit discovery."
            ),
            hint="Use --task <module:TaskClass> and repeat --task for multiple task classes.",
            details={"task_ref": entrypoint},
        )

    module_name, _, attr_name = entrypoint.partition(":")
    if not module_name or not attr_name:
        raise DiscoveryError(
            code=CODE_DISCOVERY_PROCESS_FAILED,
            message=f"Invalid task reference format: '{entrypoint}'. Both module and class must be non-empty.",
            hint="Use --task <module:TaskClass>.",
            details={"task_ref": entrypoint},
        )

    return module_name, attr_name


def _import_attribute(module_name: str, attr_name: str) -> Any:
    module = importlib.import_module(module_name)
    return getattr(module, attr_name)


def _extract_task_info(task_class: type, source_ref: str) -> DiscoveredTask:
    try:
        meta = TaskMeta.for_task(task_class)
    except ValueError as error:
        raise DiscoveryError(
            code=CODE_TASK_IDENTIFIER_INVALID,
            message=str(error),
            details={"task_ref": source_ref},
        ) from error

    return DiscoveredTask(
        name=meta.identifier.name,
        version=meta.identifier.version,
        display=task_class.__name__,
        source_ref=source_ref,
    )


def _discover_explicit_tasks(task_refs: list[str]) -> list[DiscoveredTask]:
    tasks: list[DiscoveredTask] = []

    for task_ref in task_refs:
        module_name, attr_name = _parse_entrypoint(task_ref)
        try:
            task_class = _import_attribute(module_name, attr_name)
        except (ImportError, AttributeError) as error:
            raise DiscoveryError(
                code=CODE_DISCOVERY_PROCESS_FAILED,
                message=f"Failed to import task reference '{task_ref}': {error}",
                details={"task_ref": task_ref},
            ) from error

        if not (isinstance(task_class, type) and issubclass(task_class, Task)):
            raise DiscoveryError(
                code=CODE_DISCOVERY_PROCESS_FAILED,
                message=f"Task reference '{task_ref}' does not resolve to a Task subclass.",
                details={"task_ref": task_ref},
            )

        tasks.append(_extract_task_info(task_class, task_ref))

    return tasks


def _validate_discovered_tasks(tasks: list[DiscoveredTask]) -> list[DiscoveredTask]:
    if not tasks:
        raise DiscoveryError(
            code=CODE_NO_TASKS_DISCOVERED,
            message="No tasks discovered.",
            hint="Provide at least one valid --task <module:TaskClass> reference.",
        )

    seen: set[tuple[str, str]] = set()
    for task in tasks:
        key = (task.name, task.version)
        if key in seen:
            raise DiscoveryError(
                code=CODE_TASK_IDENTIFIER_DUPLICATE,
                message=f"Duplicate task identifier discovered: name='{task.name}', version='{task.version}'.",
                details={"name": task.name, "version": task.version},
            )
        seen.add(key)

    return sorted(tasks, key=lambda task: (task.name, task.version, task.display, task.source_ref))


def discover(discovery_kind: str, explicit_tasks: list[str] | None) -> list[DiscoveredTask]:
    if discovery_kind != DISCOVERY_KIND_PYTHON_EXPLICIT:
        raise DiscoveryError(
            code=CODE_DISCOVERY_PROCESS_FAILED,
            message=(
                f"Unsupported discovery kind '{discovery_kind}'. "
                f"Expected '{DISCOVERY_KIND_PYTHON_EXPLICIT}'."
            ),
        )

    return _validate_discovered_tasks(_discover_explicit_tasks(explicit_tasks or []))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tilebox_publish_discover",
        description="Discover publishable Tilebox task identifiers from a Python project.",
    )
    parser.add_argument(
        "--protocol",
        default=DISCOVERY_PROTOCOL,
        help=f"Discovery protocol version. Defaults to '{DISCOVERY_PROTOCOL}'.",
    )
    parser.add_argument(
        "--runtime-kind",
        default=RUNTIME_KIND_PYTHON_UV,
        help=f"Runtime kind. Defaults to '{RUNTIME_KIND_PYTHON_UV}'.",
    )
    parser.add_argument(
        "--discovery-kind",
        default=DISCOVERY_KIND_PYTHON_EXPLICIT,
        help=f"Discovery strategy kind. Supported: '{DISCOVERY_KIND_PYTHON_EXPLICIT}'.",
    )
    parser.add_argument(
        "--task",
        "--explicit-task",
        action="append",
        default=None,
        dest="explicit_tasks",
        help="Task reference in the form 'module:TaskClass' (repeatable).",
    )
    return parser


def _validate_cli_args(protocol: str, runtime_kind: str, discovery_kind: str) -> None:
    if protocol != DISCOVERY_PROTOCOL:
        raise DiscoveryError(
            code=CODE_DISCOVERY_PROCESS_FAILED,
            message=f"Unsupported discovery protocol '{protocol}'. Expected '{DISCOVERY_PROTOCOL}'.",
            details={"protocol": protocol},
        )

    if runtime_kind != RUNTIME_KIND_PYTHON_UV:
        raise DiscoveryError(
            code=CODE_DISCOVERY_PROCESS_FAILED,
            message=f"Unsupported runtime kind '{runtime_kind}'. Expected '{RUNTIME_KIND_PYTHON_UV}'.",
            details={"runtime_kind": runtime_kind},
        )

    if discovery_kind != DISCOVERY_KIND_PYTHON_EXPLICIT:
        raise DiscoveryError(
            code=CODE_DISCOVERY_PROCESS_FAILED,
            message=(
                f"Unsupported discovery kind '{discovery_kind}'. "
                f"Expected '{DISCOVERY_KIND_PYTHON_EXPLICIT}'."
            ),
            details={"discovery_kind": discovery_kind},
        )


def _success_payload(
    protocol: str,
    runtime_kind: str,
    discovery_kind: str,
    tasks: list[DiscoveredTask],
) -> dict[str, object]:
    return {
        "ok": True,
        "protocol": protocol,
        "runtime_kind": runtime_kind,
        "discovery_kind": discovery_kind,
        "tasks": [asdict(task) for task in tasks],
        "warnings": [],
    }


def _error_payload(
    protocol: str,
    runtime_kind: str,
    discovery_kind: str,
    error: DiscoveryError,
) -> dict[str, object]:
    return {
        "ok": False,
        "protocol": protocol,
        "runtime_kind": runtime_kind,
        "discovery_kind": discovery_kind,
        "code": error.code,
        "message": error.message,
        "hint": error.hint,
        "details": error.details,
    }


def main() -> int:
    """CLI entry point. Returns process exit code."""
    parser = _build_parser()
    args = parser.parse_args()

    try:
        _validate_cli_args(
            protocol=args.protocol,
            runtime_kind=args.runtime_kind,
            discovery_kind=args.discovery_kind,
        )

        # Keep stdout reserved for machine-readable protocol JSON.
        with contextlib.redirect_stdout(sys.stderr):
            tasks = discover(
                discovery_kind=args.discovery_kind,
                explicit_tasks=args.explicit_tasks,
            )
    except DiscoveryError as error:
        payload = _error_payload(
            protocol=args.protocol,
            runtime_kind=args.runtime_kind,
            discovery_kind=args.discovery_kind,
            error=error,
        )
        json.dump(payload, sys.stdout)
        sys.stdout.write("\n")
        return 2
    except Exception as error:  # noqa: BLE001
        unexpected = DiscoveryError(
            code=CODE_DISCOVERY_PROCESS_FAILED,
            message=f"Unexpected discovery helper failure: {error}",
            details={"exception_type": type(error).__name__},
        )
        payload = _error_payload(
            protocol=args.protocol,
            runtime_kind=args.runtime_kind,
            discovery_kind=args.discovery_kind,
            error=unexpected,
        )
        json.dump(payload, sys.stdout)
        sys.stdout.write("\n")
        return 3
    else:
        payload = _success_payload(
            protocol=args.protocol,
            runtime_kind=args.runtime_kind,
            discovery_kind=args.discovery_kind,
            tasks=tasks,
        )
        json.dump(payload, sys.stdout)
        sys.stdout.write("\n")
        return 0
