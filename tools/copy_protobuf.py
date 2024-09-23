#!/usr/bin/env python

"""
A small utility script to copy generated protobuf messages from the core repository into this repository

This will put them in the right place, and automatically fix the imports as well

Usage (from repo root):
uv run copy-protobuf <path-to-core-repo> <path-to-go-repo> <path-to-clients-repo>
"""

import sys
from pathlib import Path

_SERVICE_MODULES = {
    "datasets-service": {
        "datasets": {
            "core": Path("tilebox-datasets/tilebox/datasets/datasetsv1"),
            "well_known_types": Path("tilebox-datasets/tilebox/datasets/datasetsv1"),
            "tilebox": Path("tilebox-datasets/tilebox/datasets/datasetsv1"),
        },
    },
    "workflows-service": {
        "workflows": {
            "core": Path("tilebox-workflows/tilebox/workflows/workflowsv1"),
            "diagram": Path("tilebox-workflows/tilebox/workflows/workflowsv1"),
            "job": Path("tilebox-workflows/tilebox/workflows/workflowsv1"),
            "task": Path("tilebox-workflows/tilebox/workflows/workflowsv1"),
            "timeseries": Path("tilebox-workflows/tilebox/workflows/workflowsv1"),
            "recurrent_task": Path("tilebox-workflows/tilebox/workflows/workflowsv1"),
            "workflows": Path("tilebox-workflows/tilebox/workflows/workflowsv1"),
        },
    },
}


def main() -> None:
    clients_repo = Path(__file__).parent.parent
    core_repo = clients_repo.parent / "core"
    go_repo = clients_repo.parent / "tilebox-go"

    if len(sys.argv) == 4:  # manual arg parsing, don't want any dependencies for this simple script
        core_repo = Path(sys.argv[1])
        go_repo = Path(sys.argv[2])
        clients_repo = Path(sys.argv[3])
    elif len(sys.argv) != 1:
        print("Usage: uv run copy-protobuf <core-repo> <go-repo> <clients-repo>")  # noqa: T201
        sys.exit(1)

    for service_folder, packages in _SERVICE_MODULES.items():
        for package, modules in packages.items():
            for module in modules:
                copy_module(
                    core_repo / service_folder / "protogen" / "python" / package / "v1",
                    clients_repo,
                    service_folder,
                    package,
                    module,
                )

        for package, modules in packages.items():
            for module in modules:
                copy_module(
                    go_repo / "protogen" / "python" / package / "v1",
                    clients_repo,
                    service_folder,
                    package,
                    module,
                )


def copy_module(search_path: Path, clients_repo: Path, service_folder: str, package: str, module: str) -> None:
    target_path = clients_repo / _SERVICE_MODULES[service_folder][package][module]
    for file in search_path.glob(f"{module}*"):
        target_file = target_path / file.name
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_text(fix_imports(file.read_text()))
        print(f"Copied and fixed file: {target_file}")  # noqa: T201


def fix_imports(content: str) -> str:
    for packages in _SERVICE_MODULES.values():
        for package, modules in packages.items():
            for module in modules:
                parts = modules[module].parts
                index = parts.index("_tilebox") if "_tilebox" in parts else parts.index("tilebox")
                tilebox_module = ".".join(parts[index:])

                content = content.replace(
                    f"from {package}.v1 import {module}", f"from {tilebox_module} import {module}"
                )
    return content.strip() + "\n"  # end of file -> new line fix


if __name__ == "__main__":
    main()
