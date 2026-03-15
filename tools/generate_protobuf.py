# ruff: noqa: INP001

"""
A small utility script to generate protobuf files.

This will put them in the right place, and automatically fix the imports as well.

Usage (from repo root):
uv run generate-protobuf <path-to-tilebox-python-repo>
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


def _buf_env() -> dict[str, str]:
    env = os.environ.copy()
    env.pop("BUF_TOKEN", None)
    return env


def _run_buf_generate(repo: Path, template: str) -> None:
    buf_binary = shutil.which("buf")
    if buf_binary is None:
        msg = "buf binary is required but was not found in PATH"
        raise RuntimeError(msg)

    subprocess.run(  # noqa: S603
        [buf_binary, "generate", "--template", template],
        check=True,
        cwd=repo,
        env=_buf_env(),
    )


def _generate_internal_worker_protobuf(clients_repo: Path) -> None:
    workspace_root = clients_repo.parent
    core_proto_dir = workspace_root / "core" / "workflows-service" / "apis-internal"
    if not core_proto_dir.exists():
        print(f"Skipping internal worker protobuf generation: {core_proto_dir} not found")  # noqa: T201
        return

    _run_buf_generate(workspace_root, str(clients_repo / "buf.gen.worker-internal.yaml"))

    # NOTE: This broad generate + delete approach can mask unintended over-generation
    # changes in review. Prefer template scoping to tilebox/runner/worker/v1 when feasible.
    # The internal proto module also contains workflows_internal protos that are not consumed
    # by tilebox-python. Keep generation focused on the worker RPC contract.
    shutil.rmtree(clients_repo / "tilebox-workflows" / "workflows_internal", ignore_errors=True)


def main() -> None:
    clients_repo = Path(__file__).parent.parent

    if len(sys.argv) == 2:  # manual arg parsing, don't want any dependencies for this simple script
        clients_repo = Path(sys.argv[1])
    elif len(sys.argv) != 1:
        print("Usage: uv run generate-protobuf <tilebox-python-repo>")  # noqa: T201
        sys.exit(1)

    print("Running buf generate")  # noqa: T201
    _run_buf_generate(clients_repo, "buf.gen.datasets.yaml")
    _run_buf_generate(clients_repo, "buf.gen.workflows.yaml")
    _generate_internal_worker_protobuf(clients_repo)

    package_mapping = {
        "from datasets.v1 import": "from tilebox.datasets.datasets.v1 import",
        "from tilebox.v1 import": "from tilebox.datasets.tilebox.v1 import",
        "from buf.validate import": "from tilebox.datasets.buf.validate import",
        "from workflows.v1 import": "from tilebox.workflows.workflows.v1 import",
    }

    folders = (
        clients_repo / "tilebox-datasets" / "tilebox" / "datasets" / "datasets" / "v1",
        clients_repo / "tilebox-datasets" / "tilebox" / "datasets" / "tilebox" / "v1",
        clients_repo / "tilebox-datasets" / "tilebox" / "datasets" / "buf" / "validate",
        clients_repo / "tilebox-workflows" / "tilebox" / "workflows" / "workflows" / "v1",
        clients_repo / "tilebox-workflows" / "tilebox" / "runner" / "worker" / "v1",
    )

    for folder in folders:
        for pattern in ("*.py", "*.pyi"):
            for py_file in folder.rglob(pattern):
                fix_imports(py_file, package_mapping)


def fix_imports(file_path: Path, package_mapping: dict[str, str]) -> None:
    """Fix imports in a single Python file."""
    content = file_path.read_text()
    original_content = content

    for old_import, new_import in package_mapping.items():
        content = content.replace(old_import, new_import)

    content = content.strip() + "\n"  # end of file -> new line fix

    if content != original_content:
        file_path.write_text(content)
        print(f"Fixed imports in: {file_path}")  # noqa: T201


if __name__ == "__main__":
    main()
