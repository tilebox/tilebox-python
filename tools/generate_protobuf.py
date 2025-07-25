#!/usr/bin/env python

"""
A small utility script to generate protobuf files.

This will put them in the right place, and automatically fix the imports as well

Usage (from repo root):
uv run generate-protobuf <path-to-tilebox-python-repo>
"""

import os
import sys
from pathlib import Path


def main() -> None:
    clients_repo = Path(__file__).parent.parent

    if len(sys.argv) == 2:  # manual arg parsing, don't want any dependencies for this simple script
        clients_repo = Path(sys.argv[1])
    elif len(sys.argv) != 1:
        print("Usage: uv run generate-protobuf <tilebox-python-repo>")  # noqa: T201
        sys.exit(1)

    print("Running buf generate")  # noqa: T201
    os.system("buf generate --template buf.gen.datasets.yaml")  # noqa: S605, S607
    os.system("buf generate --template buf.gen.workflows.yaml")  # noqa: S605, S607

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
