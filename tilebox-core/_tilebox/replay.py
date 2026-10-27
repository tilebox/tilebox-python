"""Native unary recording and replay using the four-line binary fixture format."""

import base64
from collections.abc import Awaitable, Callable
from pathlib import Path
from threading import Lock
from typing import TypeVar

from connectrpc.code import Code
from connectrpc.errors import ConnectError
from connectrpc.request import RequestContext
from protobuf import Message

Req = TypeVar("Req", bound=Message)
Res = TypeVar("Res", bound=Message)

# The fixture format stores the canonical numeric RPC status, not Connect's string enum.
_CODES = (
    None,
    Code.CANCELED,
    Code.UNKNOWN,
    Code.INVALID_ARGUMENT,
    Code.DEADLINE_EXCEEDED,
    Code.NOT_FOUND,
    Code.ALREADY_EXISTS,
    Code.PERMISSION_DENIED,
    Code.RESOURCE_EXHAUSTED,
    Code.FAILED_PRECONDITION,
    Code.ABORTED,
    Code.OUT_OF_RANGE,
    Code.UNIMPLEMENTED,
    Code.INTERNAL,
    Code.UNAVAILABLE,
    Code.DATA_LOSS,
    Code.UNAUTHENTICATED,
)


def _method(ctx: RequestContext) -> str:
    return f"/{ctx.method.service_name}/{ctx.method.name}"


class Replay:
    """Replay recorded unary calls through synchronous or asynchronous interceptors."""

    def __init__(self, recording: str | Path, assert_request_matches: bool = True) -> None:
        self._lines = iter(Path(recording).read_bytes().split(b"\n"))
        self.assert_request_matches = assert_request_matches
        self._lock = Lock()

    def _replay(self, request: Req, ctx: RequestContext[Req, Res]) -> Res:
        with self._lock:
            try:
                method, expected, status, response = (next(self._lines) for _ in range(4))
            except (StopIteration, RuntimeError) as error:
                raise ValueError(f"Replayed call to {_method(ctx)} was never recorded!") from error
        if method.decode() != _method(ctx):
            raise ValueError(f"Expected method {method.decode()}, but got {_method(ctx)}")
        if self.assert_request_matches and request != type(request).from_binary(base64.b64decode(expected)):
            raise ValueError(f"Expected request for RPC call {_method(ctx)} differs from actual received request")
        code = int(status)
        if code:
            status_code = _CODES[code]
            if status_code is None:
                raise ValueError(f"Invalid recorded status: {code}")
            raise ConnectError(status_code, response.decode())
        return ctx.method.output.from_binary(base64.b64decode(response))

    def intercept_unary_sync(
        self,
        call_next: Callable[[Req, RequestContext], Res],
        request: Req,
        ctx: RequestContext[Req, Res],
    ) -> Res:
        """Return the next recorded synchronous response."""
        _ = call_next
        return self._replay(request, ctx)

    async def intercept_unary(
        self,
        call_next: Callable[[Req, RequestContext], Awaitable[Res]],
        request: Req,
        ctx: RequestContext[Req, Res],
    ) -> Res:
        """Return the next recorded asynchronous response."""
        _ = call_next
        return self._replay(request, ctx)


class Record:
    """Record native unary successes and Connect failures for deterministic replay."""

    def __init__(self, recording: str | Path) -> None:
        self.recording = Path(recording)
        self.recording.parent.mkdir(parents=True, exist_ok=True)
        self.recording.write_bytes(b"")
        self._lock = Lock()

    def _write(
        self,
        request: Message,
        ctx: RequestContext,
        response: Message | None = None,
        error: ConnectError | None = None,
    ) -> None:
        status = _CODES.index(error.code) if error is not None else 0
        if error is not None:
            payload = error.message.encode().replace(b"\n", b" ")
        elif response is not None:
            payload = base64.b64encode(response.to_binary())
        else:
            raise ValueError("A recorded call requires a response or error")
        entry = b"\n".join(
            (_method(ctx).encode(), base64.b64encode(request.to_binary()), str(status).encode(), payload)
        )
        with self._lock, self.recording.open("ab") as file:
            file.write(entry + b"\n")

    def intercept_unary_sync(
        self,
        call_next: Callable[[Req, RequestContext], Res],
        request: Req,
        ctx: RequestContext[Req, Res],
    ) -> Res:
        """Record a synchronous unary call without changing its result."""
        try:
            response = call_next(request, ctx)
        except ConnectError as error:
            self._write(request, ctx, error=error)
            raise
        self._write(request, ctx, response=response)
        return response

    async def intercept_unary(
        self,
        call_next: Callable[[Req, RequestContext], Awaitable[Res]],
        request: Req,
        ctx: RequestContext[Req, Res],
    ) -> Res:
        """Record an asynchronous unary call without changing its result."""
        try:
            response = await call_next(request, ctx)
        except ConnectError as error:
            self._write(request, ctx, error=error)
            raise
        self._write(request, ctx, response=response)
        return response
