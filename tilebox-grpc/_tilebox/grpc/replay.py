import base64
from collections.abc import Callable, Generator
from functools import partial
from pathlib import Path
from typing import Any, Generic, TypeVar

from google.protobuf.message import Message

from _tilebox.grpc.channel import (
    _AuthMetadataInterceptor,
    _ErrorHandlerInterceptor,
    _handle_rpc_error,
    _open_channel,
    _parse_channel_info,
)
from grpc import StatusCode
from grpc.aio import (
    AioRpcError,
    Channel,
    ClientCallDetails,
    UnaryUnaryCall,
)
from grpc.aio._interceptor import UnaryUnaryClientInterceptor

RequestType = TypeVar("RequestType")
ResponseType = TypeVar("ResponseType")


def open_recording_channel(url: str, auth_token: str | None, recording: str | Path) -> Channel:
    """Open a gRPC channel to the given URL and record all requests and responses to a file."""
    channel_info = _parse_channel_info(url)
    interceptors: list[UnaryUnaryClientInterceptor] = [_ErrorHandlerInterceptor(), _RecordRPCsInterceptor(recording)]
    if auth_token is not None:
        interceptors = [_AuthMetadataInterceptor(auth_token), *interceptors]  # add auth interceptor as the first one
    return _open_channel(channel_info, interceptors)


def open_replay_channel(recording: str | Path, assert_request_matches: bool = True) -> Channel:
    return _ReplayChannel(recording, assert_request_matches)  # type: ignore[return-value]


class _RecordRPCsInterceptor(UnaryUnaryClientInterceptor):
    def __init__(self, recording: str | Path) -> None:
        self.recording = Path(recording)
        self.recording.parent.mkdir(parents=True, exist_ok=True)
        if self.recording.exists():
            self.recording.unlink()

    async def intercept_unary_unary(
        self,
        continuation: Callable[[ClientCallDetails, RequestType], UnaryUnaryCall],
        client_call_details: ClientCallDetails,
        request: RequestType,
    ) -> UnaryUnaryCall:
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
            response = await continuation(client_call_details, request)
            result = await response

            response_data = base64.b64encode(result.SerializeToString())

            with self.recording.open("ab") as file:
                file.write(str(StatusCode.OK.value[0]).encode())
                file.write(b"\n")
                file.write(response_data)
                file.write(b"\n")

        except AioRpcError as err:
            with self.recording.open("ab") as file:
                file.write(str(err.code().value[0]).encode())
                file.write(b"\n")
                error_message = err.details()
                file.write(error_message.encode() if error_message is not None else b"")
                file.write(b"\n")

            raise  # re-raise the error

        return response


class _ReplayResponse(Generic[ResponseType]):
    def __init__(self, response: Any) -> None:
        """Replay response is the response of a unary_unary call. It's a wrapper around the actual response such
        that it is awaitable."""
        self.response = response

    def __await__(self) -> Generator[Any, None, ResponseType]:
        yield
        return self.response


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
    ) -> Callable[[Message], _ReplayResponse]:
        return partial(self.unary_unary_call, method, request_serializer, response_deserializer)

    def unary_unary_call(
        self,
        method: str,
        request_serializer: Callable[[Message], bytes],
        response_deserializer: Callable[[bytes], Message],
        request: Message,
    ) -> _ReplayResponse:
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
            _handle_rpc_error(error)
            raise error  # if the AioRpcError wasn't raised as a pythonic error by handle_rpc_error, raise it directly

        response = response_deserializer(base64.b64decode(recorded_response))
        return _ReplayResponse(response)


_STATUS_CODES = {code.value[0]: code for code in StatusCode}
