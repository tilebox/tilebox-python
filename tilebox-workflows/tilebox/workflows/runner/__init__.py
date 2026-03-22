from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path
from urllib.parse import urlparse

from tilebox.workflows.cache import JobCache
from tilebox.workflows.runner.worker_rpc_server import _run_worker_rpc
from tilebox.workflows.runner.worker_rpc_v1 import PythonWorkerShim
from tilebox.workflows.task import Task as TaskInstance
from tilebox.workflows.task import TaskMeta

DISCOVERY_PROTOCOL = "tilebox.discovery.v1"
DISCOVERY_RUNTIME_KIND = "python_uv"
DISCOVERY_KIND_RUNTIME_COMMAND = "runtime_command"
CODE_NO_TASKS_DISCOVERED = "TBX-PUB-012"

_REGISTERED_TASKS: dict[tuple[str, str], type[TaskInstance]] = {}


def register(task: type[TaskInstance]) -> None:
    """Register a task class for discovery and worker execution."""
    metadata = TaskMeta.for_task(task)
    key = (metadata.identifier.name, metadata.identifier.version)
    if key in _REGISTERED_TASKS:
        msg = (
            "Duplicate task identifier: "
            f"A task '{metadata.identifier.name}' with version '{metadata.identifier.version}' is already registered."
        )
        raise ValueError(msg)

    _REGISTERED_TASKS[key] = task


def registered_tasks() -> tuple[type[TaskInstance], ...]:
    """Return the current global task registry in deterministic order."""
    keys = sorted(_REGISTERED_TASKS)
    return tuple(_REGISTERED_TASKS[key] for key in keys)


def _source_ref_for_task(task: type[TaskInstance]) -> str:
    return f"{task.__module__}:{task.__name__}"


def _discovery_tasks_payload() -> list[dict[str, str]]:
    payload: list[dict[str, str]] = []
    for task in registered_tasks():
        metadata = TaskMeta.for_task(task)
        payload.append(
            {
                "name": metadata.identifier.name,
                "version": metadata.identifier.version,
                "display": task.__name__,
                "source_ref": _source_ref_for_task(task),
            }
        )

    return payload


def _emit_payload(payload: dict[str, object]) -> None:
    print(json.dumps(payload, separators=(",", ":")), flush=True)


def _run_discovery() -> int:
    tasks = _discovery_tasks_payload()
    if len(tasks) == 0:
        _emit_payload(
            {
                "ok": False,
                "protocol": DISCOVERY_PROTOCOL,
                "runtime_kind": DISCOVERY_RUNTIME_KIND,
                "discovery_kind": DISCOVERY_KIND_RUNTIME_COMMAND,
                "code": CODE_NO_TASKS_DISCOVERED,
                "message": "No tasks discovered.",
                "hint": "Register at least one task before calling runner.main().",
                "details": {},
            }
        )
        return 1

    _emit_payload(
        {
            "ok": True,
            "protocol": DISCOVERY_PROTOCOL,
            "runtime_kind": DISCOVERY_RUNTIME_KIND,
            "discovery_kind": DISCOVERY_KIND_RUNTIME_COMMAND,
            "tasks": tasks,
            "warnings": [],
        }
    )
    return 0


def _google_storage_cache(bucket: str, prefix: str) -> JobCache:
    from google.cloud.storage import Client as StorageClient  # noqa: PLC0415
    from tilebox.workflows.cache import GoogleStorageCache  # noqa: PLC0415

    storage_client = StorageClient(project=os.getenv("GOOGLE_CLOUD_PROJECT"))
    return GoogleStorageCache(storage_client.bucket(bucket), prefix=prefix)


def _parse_cache_uri(uri: str) -> tuple[str, str, str | None]:
    parsed = urlparse(uri)
    scheme = parsed.scheme.lower()
    bucket_or_host = parsed.netloc.strip()
    parsed_path = parsed.path.strip().strip("/")
    return scheme, bucket_or_host, parsed_path or None


def _resolve_worker_cache() -> JobCache:
    configured_cache = os.getenv("TILEBOX_WORKER_CACHE", "").strip()
    if configured_cache == "" or configured_cache.lower() == "inmemory":
        from tilebox.workflows.cache import InMemoryCache  # noqa: PLC0415

        return InMemoryCache()

    cache_lower = configured_cache.lower()
    if cache_lower == "none":
        from tilebox.workflows.cache import NoCache  # noqa: PLC0415

        return NoCache()
    if cache_lower == "filesystem":
        from tilebox.workflows.cache import LocalFileSystemCache  # noqa: PLC0415

        return LocalFileSystemCache(Path("./cache"))

    scheme, bucket_or_host, parsed_path = _parse_cache_uri(configured_cache)
    if scheme == "file":
        if bucket_or_host != "":
            msg = (
                "Invalid TILEBOX_WORKER_CACHE value for filesystem cache. "
                "Use file:///absolute/path (for example file:///opt/tilebox/cache)."
            )
            raise ValueError(msg)

        filesystem_root = f"/{parsed_path}" if parsed_path else "/"
        from tilebox.workflows.cache import LocalFileSystemCache  # noqa: PLC0415

        return LocalFileSystemCache(Path(filesystem_root))

    if scheme in {"s3", "gs", "gcs"}:
        if bucket_or_host == "":
            msg = "TILEBOX_WORKER_CACHE must include a bucket for s3://, gs://, and gcs:// values."
            raise ValueError(msg)

        cache_prefix = parsed_path or "jobs"
        if scheme in {"gs", "gcs"}:
            return _google_storage_cache(bucket_or_host, cache_prefix)
        from tilebox.workflows.cache import AmazonS3Cache  # noqa: PLC0415

        return AmazonS3Cache(bucket_or_host, prefix=cache_prefix)

    msg = (
        "Invalid TILEBOX_WORKER_CACHE value. "
        "Use one of: inmemory, none, filesystem, file:///absolute/path, s3://bucket[/prefix], gs://bucket[/prefix], gcs://bucket[/prefix]."
    )
    raise ValueError(msg)


def _run_worker() -> int:
    rpc_address = os.getenv("TILEBOX_WORKER_RPC_ADDRESS")
    if not rpc_address:
        print("TILEBOX_WORKER_RPC_ADDRESS must be set", file=sys.stderr)
        return 1

    tasks = list(registered_tasks())
    if len(tasks) == 0:
        print("No tasks registered; call runner.register(...) before runner.main()", file=sys.stderr)
        return 1

    shim = PythonWorkerShim(
        tasks=tasks,
        cache=_resolve_worker_cache(),
        expected_environment_digest=os.getenv("TILEBOX_WORKER_ENVIRONMENT_DIGEST") or None,
        expected_artifact_digest=os.getenv("TILEBOX_WORKER_ARTIFACT_DIGEST") or None,
        expected_entrypoint=os.getenv("TILEBOX_WORKER_ENTRYPOINT") or None,
    )
    _run_worker_rpc(shim=shim, address=rpc_address)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Run discovery (`--tilebox-discover`) or start worker RPC server."""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--tilebox-discover", action="store_true")
    args, _ = parser.parse_known_args(argv)

    if args.tilebox_discover:
        return _run_discovery()

    return _run_worker()


__all__ = ["PythonWorkerShim", "main", "register", "registered_tasks"]
