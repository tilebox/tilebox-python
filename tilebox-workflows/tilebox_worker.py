# ruff: noqa: INP001

from tilebox.workflows.runner.worker_rpc_server import main

__all__ = ["main"]


if __name__ == "__main__":
    raise SystemExit(main())
