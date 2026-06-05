import argparse
import importlib
from collections.abc import Sequence
from typing import Any

from tilebox.workflows.runner.runner import Runner
from tilebox.workflows.runner.worker_server import serve_runner


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m tilebox.workflows.runner",
        description="Start a Tilebox workflow worker runtime.",
    )
    parser.add_argument("runner", help="Runner object import path, for example 'my_workflow.runner:runner'.")
    args = parser.parse_args(argv)

    serve_runner(_import_runner(args.runner))
    return 0


def _import_runner(import_path: str) -> Runner:
    module_name, separator, object_path = import_path.partition(":")
    if not module_name or not separator or not object_path:
        raise SystemExit(
            "Expected runner import path in the format '<module>:<object>', for example 'my_workflow.runner:runner'."
        )

    try:
        module = importlib.import_module(module_name)
    except Exception as error:
        raise SystemExit(f"Failed to import module {module_name!r}: {error}") from error

    try:
        obj = _get_attribute(module, object_path)
    except AttributeError as error:
        raise SystemExit(f"Module {module_name!r} has no runner object {object_path!r}.") from error

    if not isinstance(obj, Runner):
        raise SystemExit(
            f"Expected {import_path!r} to resolve to tilebox.workflows.Runner, "
            f"got {type(obj).__module__}.{type(obj).__qualname__}."
        )

    return obj


def _get_attribute(obj: Any, dotted_path: str) -> Any:
    for part in dotted_path.split("."):
        obj = getattr(obj, part)
    return obj


if __name__ == "__main__":
    raise SystemExit(main())
