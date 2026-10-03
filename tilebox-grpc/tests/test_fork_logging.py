"""Check native gRPC diagnostics when a CLI starts during active RPCs.

Run on macOS to check RPCs and report the known fork-log issue:

uv run --isolated --no-project --with grpcio==1.84.0 --with pytest pytest -c /dev/null -p no:cacheprovider -rx tilebox-grpc/tests/test_fork_logging.py

RPC failures fail the test. Known fork diagnostics produce XFAIL after the RPC checks pass.
Linux may use vfork and not reproduce the diagnostics. This check uses no cloud credentials.
"""

import os
import subprocess
import sys
from textwrap import dedent

import pytest


# RPCs must survive CLI subprocess launches; known fork-log noise is reported separately.
@pytest.mark.skipif(sys.platform == "win32", reason="Windows does not use POSIX fork handlers")
def test_cli_spawn_during_rpcs() -> None:
    result = subprocess.run(  # noqa: S603
        [
            sys.executable,
            "-c",
            dedent("""
                import subprocess
                import sys
                from concurrent.futures import ThreadPoolExecutor
                from threading import Event

                import grpc

                with ThreadPoolExecutor(max_workers=4) as executor:
                    server = grpc.server(executor)
                    server.add_generic_rpc_handlers((grpc.method_handlers_generic_handler(
                        "probe", {"echo": grpc.unary_unary_rpc_method_handler(lambda request, context: request)}
                    ),))
                    port = server.add_insecure_port("127.0.0.1:0")
                    server.start()
                    stop = Event()
                    try:
                        with grpc.insecure_channel(f"127.0.0.1:{port}") as channel:
                            echo = channel.unary_unary("/probe/echo")
                            assert echo(b"before", timeout=5) == b"before"

                            def poll():
                                while not stop.is_set():
                                    assert echo(b"during", timeout=5) == b"during"

                            poller = executor.submit(poll)
                            try:
                                for _ in range(25):
                                    # Azure CLI authentication supplies cwd, which prevents posix_spawn.
                                    subprocess.run([sys.executable, "-c", "pass"], cwd=".", check=True, timeout=5)
                            finally:
                                stop.set()
                                poller.result(timeout=10)
                            assert echo(b"after", timeout=5) == b"after"
                    finally:
                        stop.set()
                        server.stop(0).wait(10)
            """),
        ],
        capture_output=True,
        text=True,
        timeout=60,
        env={**os.environ, "GRPC_VERBOSITY": "INFO"},
        check=False,
    )
    assert result.returncode == 0, result.stderr
    if "FD from fork parent still in poll list" in result.stderr:
        pytest.xfail("Known gRPC fork diagnostics: https://github.com/grpc/grpc/issues/42293")
