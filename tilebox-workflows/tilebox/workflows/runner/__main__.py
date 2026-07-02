import argparse
import importlib
import os
import sys
from collections.abc import Sequence
from time import perf_counter
from typing import Any

from loguru import logger

from tilebox.workflows.runner.runner import Runner
from tilebox.workflows.runner.worker_server import serve_runner


def main(argv: Sequence[str] | None = None) -> int:
    _configure_logging()

    parser = argparse.ArgumentParser(
        prog="python -m tilebox.workflows.runner",
        description="Start a Tilebox workflow worker runtime.",
    )
    parser.add_argument("runner", help="Runner object import path, for example 'my_workflow.runner:runner'.")
    args = parser.parse_args(argv)

    logger.debug(f"Starting Tilebox workflow runtime for runner {args.runner!r}")
    runner = _import_runner(args.runner)
    logger.debug(f"Imported runner {args.runner!r}; starting worker server")
    serve_runner(runner)
    logger.debug("Worker server stopped")
    return 0


def _configure_logging() -> None:
    level = "DEBUG" if _is_debug_enabled() else "INFO"
    logger.remove()
    logger.add(sys.stderr, level=level, format="{process}: {level}: {message}", catch=True)


def _is_debug_enabled() -> bool:
    value = os.environ.get("TILEBOX_DEBUG")
    if value is None:
        return False
    return value.strip().lower() in {"", "1", "true", "yes", "on"}


def _import_runner(import_path: str) -> Runner:
    module_name, separator, object_path = import_path.partition(":")
    if not module_name or not separator or not object_path:
        raise SystemExit(
            "Expected runner import path in the format '<module>:<object>', for example 'my_workflow.runner:runner'."
        )

    logger.debug(f"Importing runner module {module_name!r}")
    import_started_at = perf_counter()
    try:
        module = importlib.import_module(module_name)
    except Exception as error:
        import_duration = perf_counter() - import_started_at
        raise SystemExit(
            f"Failed to import module {module_name!r}: {error} (attempted import took {import_duration:.3f}s)"
        ) from error
    import_duration = perf_counter() - import_started_at
    logger.debug(f"Imported runner module {module_name!r} in {import_duration:.3f}s")

    logger.debug(f"Resolving runner object {object_path!r} from module {module_name!r}")
    try:
        obj = _get_attribute(module, object_path)
    except AttributeError as error:
        raise SystemExit(f"Module {module_name!r} has no runner object {object_path!r}.") from error
    logger.debug(f"Resolved runner object {object_path!r} from module {module_name!r}")

    if not isinstance(obj, Runner):
        raise SystemExit(
            f"Expected {import_path!r} to resolve to tilebox.workflows.Runner, "
            f"got {type(obj).__module__}.{type(obj).__qualname__}."
        )

    logger.debug(f"Runner {import_path!r} registered {len(obj.task_identifiers)} task(s)")
    return obj


def _get_attribute(obj: Any, dotted_path: str) -> Any:
    for part in dotted_path.split("."):
        obj = getattr(obj, part)
    return obj


if __name__ == "__main__":
    raise SystemExit(main())
