#!/usr/bin/env python

"""
A small utility script to copy generated protobuf messages from the core repository into this repository

This will put them in the right place, and automatically fix the imports as well

Usage (from repo root):
uv run copy-protobuf <path-to-tilebox-go-repo> <path-to-tilebox-python-repo>

Requires tilebox-go (https://github.com/tilebox/tilebox-go) to be checked out, and protos to be generated.
This can be done by running `go generate ./...` in the root of the tilebox-go repository.
"""

import sys
from pathlib import Path

_MODULES_TO_COPY = {
    "datasets": {
        "tilebox-datasets/tilebox/datasets/datasetsv1": [
            "collections",
            "core",
            "data_access",
            "data_ingestion",
            "dataset_type",
            "datasets",
            "timeseries",
            "well_known_types",
        ],
    },
    "workflows": {
        "tilebox-workflows/tilebox/workflows/workflowsv1": [
            "automation",
            "core",
            "diagram",
            "job",
            "task",
            "workflows",
        ],
    },
}


def main() -> None:
    clients_repo = Path(__file__).parent.parent
    go_repo = clients_repo.parent / "tilebox-go"

    if len(sys.argv) == 3:  # manual arg parsing, don't want any dependencies for this simple script
        go_repo = Path(sys.argv[1])
        clients_repo = Path(sys.argv[2])
    elif len(sys.argv) != 1:
        print("Usage: uv run copy-protobuf <tilebox-go-repo> <tilebox-python-repo>")  # noqa: T201
        sys.exit(1)

    for root_module, copy_operations in _MODULES_TO_COPY.items():
        for target_path, modules in copy_operations.items():
            for module in modules:
                copy_module(
                    go_repo / "protogen" / "python" / root_module / "v1",
                    clients_repo / target_path,
                    module,
                )


def copy_module(search_path: Path, target_path: Path, module: str) -> None:
    for file in search_path.glob(f"{module}*"):
        target_file = target_path / file.name
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_text(fix_imports(file.read_text()))
        print(f"Copied and fixed file: {target_file}")  # noqa: T201


def fix_imports(content: str) -> str:
    for root_module, copy_operations in _MODULES_TO_COPY.items():
        for target_path, modules in copy_operations.items():
            parts = Path(target_path).parts
            index = parts.index("_tilebox") if "_tilebox" in parts else parts.index("tilebox")
            tilebox_module = ".".join(parts[index:])

            for module in modules:
                content = content.replace(
                    f"from {root_module}.v1 import {module}", f"from {tilebox_module} import {module}"
                )
    return content.strip() + "\n"  # end of file -> new line fix


if __name__ == "__main__":
    main()
