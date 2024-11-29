import base64
from collections.abc import Callable
from functools import partial
from pathlib import Path
from typing import Any, TypeVar, cast

from google.protobuf.message import Message

from _tilebox.grpc.channel import (
    _AuthMetadataInterceptor,
    _open_channel,
    parse_channel_info,
)
from _tilebox.grpc.error import AnyRpcError
from grpc import (
    Channel,
    Future,
    RpcError,
    StatusCode,
    UnaryUnaryClientInterceptor,
    intercept_channel,
)
from grpc.aio import (
    AioRpcError,
    ClientCallDetails,  # import from aio, since grpc.ClientCallDetails is an empty base class
)

RequestType = TypeVar("RequestType")
ResponseType = TypeVar("ResponseType")


def open_recording_channel(url: str, auth_token: str | None, recording: str | Path) -> Channel:
    """Open a gRPC channel to the given URL and record all requests and responses to a file."""
    channel_info = parse_channel_info(url)
    interceptors: list[UnaryUnaryClientInterceptor] = [_RecordRPCsInterceptor(recording)]
    if auth_token is not None:
        interceptors = [_AuthMetadataInterceptor(auth_token), *interceptors]  # add auth interceptor as the first one

    return intercept_channel(_open_channel(channel_info), *interceptors)


def open_replay_channel(recording: str | Path, assert_request_matches: bool = True) -> Channel:
    return _ReplayChannel(recording, assert_request_matches)  # type: ignore[return-value]


class _ConcreteValue(Future):
    def __init__(self, result: Message) -> None:
        self._result = result

    def cancel(self) -> bool:
        return False

    def cancelled(self) -> bool:
        return False

    def running(self) -> bool:
        return False

    def done(self) -> bool:
        return True

    def result(self, timeout: float | None = None) -> Message:
        _ = timeout
        return self._result

    def exception(self, timeout: float | None = None) -> BaseException | None:
        _ = timeout
        return None

    def traceback(self, timeout: float | None = None) -> None:
        _ = timeout

    def add_done_callback(self, fn: Callable[[Message], None]) -> None:
        fn(self._result)


class _RecordRPCsInterceptor(UnaryUnaryClientInterceptor):
    def __init__(self, recording: str | Path) -> None:
        self.recording = Path(recording)
        self.recording.parent.mkdir(parents=True, exist_ok=True)
        if self.recording.exists():
            self.recording.unlink()

    def intercept_unary_unary(
        self,
        continuation: Callable[[ClientCallDetails, RequestType], Future],
        client_call_details: ClientCallDetails,
        request: RequestType,
    ) -> Future:
        request_data = base64.b64encode(request.SerializeToString())  # type: ignore[attr-defined]
        with self.recording.open("ab") as file:
            method = client_call_details.method
            if isinstance(method, str):
                method = method.encode()
            file.write(method)
            file.write(b"\n")
            file.write(request_data)
            file.write(b"\n")

        try:
            outcome = continuation(client_call_details, request)
            result: Message = outcome.result()
            response_data = base64.b64encode(result.SerializeToString())

            with self.recording.open("ab") as file:
                file.write(str(StatusCode.OK.value[0]).encode())
                file.write(b"\n")
                file.write(response_data)
                file.write(b"\n")

        except (RpcError, AioRpcError) as err:
            err = cast(AnyRpcError, err)
            with self.recording.open("ab") as file:
                file.write(str(err.code().value[0]).encode())
                file.write(b"\n")
                error_message = err.details()
                file.write(error_message.encode() if error_message is not None else b"")
                file.write(b"\n")

            raise  # re-raise the error

        return outcome


class _ReplayChannel:
    def __init__(self, recording: str | Path, assert_request_matches: bool = True) -> None:
        self.recording = Path(recording).read_bytes().split(b"\n")
        self.assert_request_matches = assert_request_matches

    def unary_unary(
        self,
        method: str,
        request_serializer: Callable[[Message], bytes],
        response_deserializer: Callable[[bytes], Message],
        **kwargs: dict[str, Any],  # noqa: ARG002
    ) -> Callable[[Message], Message]:
        return partial(self.unary_unary_call, method, request_serializer, response_deserializer)

    def unary_unary_call(
        self,
        method: str,
        request_serializer: Callable[[Message], bytes],
        response_deserializer: Callable[[bytes], Message],
        request: Message,
    ) -> Message:
        if len(self.recording) < 4:
            raise ValueError(f"Replayed call to {method} was never recorded!")
        recorded_method = self.recording.pop(0).decode()
        recorded_request = self.recording.pop(0)
        recorded_status = int(self.recording.pop(0).decode())
        recorded_response = self.recording.pop(0)

        if recorded_method != method:
            raise ValueError(f"Expected method {method}, but got {recorded_method}")

        if self.assert_request_matches:
            actual_request = request_serializer(request)
            if actual_request != base64.b64decode(recorded_request):
                raise ValueError(
                    f"Expected request for RPC call {recorded_method} differs from actual received request"
                )

        if recorded_status != StatusCode.OK.value[0]:  # the recorded call was an error, so raise it again
            code = _STATUS_CODES[recorded_status]
            error = AioRpcError(code, None, None, recorded_response.decode())  # type: ignore[arg-type]
            raise error

        return response_deserializer(base64.b64decode(recorded_response))


_STATUS_CODES = {code.value[0]: code for code in StatusCode}
