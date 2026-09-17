"""Local structured logging for CLI-managed workflow runtimes."""

import contextlib
import logging
import os
import queue
import select
import threading
import time
import traceback
from typing import Any

import msgspec

from tilebox.workflows.observability._logging import _record_attributes


class _PipeWriter:
    def __init__(self, fd: int) -> None:
        self._fd = fd
        self._closing = threading.Event()
        self._submit_lock = threading.Lock()
        self._dropped = 0
        self._records: queue.Queue[bytes | None] = queue.Queue(maxsize=256)
        self._thread = threading.Thread(target=self._run, name="tilebox-log-writer", daemon=True)
        os.set_inheritable(fd, False)
        os.set_blocking(fd, False)
        self._thread.start()

    def submit(self, record: dict[str, Any]) -> None:
        with self._submit_lock:
            if self._closing.is_set():
                return
            if self._records.full():
                self._dropped += 1
                return
            data = msgspec.json.encode(record) + b"\n"
            if len(data) > 1024 * 1024:
                data = b'{"level":"warning","message":"Local log record exceeded 1 MiB; discarded"}\n'
            try:
                if self._dropped:
                    notice = {"level": "warning", "message": f"Dropped {self._dropped} local log records"}
                    self._records.put_nowait(msgspec.json.encode(notice) + b"\n")
                    self._dropped = 0
                self._records.put_nowait(data)
            except queue.Full:
                self._dropped += 1

    def close(self) -> None:
        with self._submit_lock:
            if not self._closing.is_set():
                self._closing.set()
                # Wake an idle writer. A full queue already keeps it awake until
                # it drains, when the closing flag ends the loop instead.
                with contextlib.suppress(queue.Full):
                    self._records.put_nowait(None)
        self._thread.join(timeout=0.5)

    def _run(self) -> None:
        try:
            self._drain()
        finally:
            with self._submit_lock:
                self._closing.set()
                # Disconnected or stalled readers must not retain queued payloads.
                while not self._records.empty():
                    self._records.get_nowait()
            with contextlib.suppress(OSError):
                os.close(self._fd)

    def _drain(self) -> None:
        while not self._closing.is_set() or not self._records.empty():
            item = self._records.get()
            if item is None:
                return
            # Coalesce queued records without waiting for more. This avoids two
            # syscalls per small message while keeping idle delivery immediate.
            batch = [item]
            size = len(item)
            while size < 64 * 1024:
                try:
                    item = self._records.get_nowait()
                except queue.Empty:
                    break
                if item is None:
                    break
                batch.append(item)
                size += len(item)
            view = memoryview(b"".join(batch))
            deadline = time.monotonic() + 0.25
            while view and time.monotonic() < deadline:
                try:
                    _, writable, _ = select.select([], [self._fd], [], 0.05)
                    if writable:
                        view = view[os.write(self._fd, view) :]
                except (BrokenPipeError, OSError, ValueError):  # noqa: PERF203 -- every write may break
                    return
            if view:
                # Never append another record after a partial timed-out write.
                return


class _StructuredHandler(logging.Handler):
    def __init__(self, writer: _PipeWriter) -> None:
        super().__init__(logging.NOTSET)
        self._writer = writer

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._emit(record)
        except Exception:  # noqa: BLE001 -- a local logging failure must not fail a task
            self.handleError(record)

    def _emit(self, record: logging.LogRecord) -> None:
        output: dict[str, Any] = {
            "level": record.levelname.lower(),
            "message": record.getMessage(),
        }
        if record.exc_info:
            output["exception"] = "".join(traceback.format_exception(*record.exc_info)).rstrip("\n")
        attributes = _record_attributes(record)
        if attributes:
            output["attributes"] = attributes
        self._writer.submit(output)
