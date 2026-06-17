from typing import TypeVar

import pytest
from grpc import StatusCode
from grpc.aio import AioRpcError
from grpc.aio._metadata import Metadata

from _tilebox.grpc.error import (
    ArgumentError,
    AuthenticationError,
    InternalServerError,
    NotFoundError,
    TooManyRequestsError,
    translate_connect_error,
    with_pythonic_errors,
)

E = TypeVar("E", bound=BaseException)


@pytest.mark.parametrize(
    ("grpc_status", "exception_type"),
    [
        (StatusCode.UNAUTHENTICATED, AuthenticationError),
        (StatusCode.PERMISSION_DENIED, AuthenticationError),
        (StatusCode.NOT_FOUND, NotFoundError),
        (StatusCode.INVALID_ARGUMENT, ArgumentError),
        (StatusCode.INTERNAL, InternalServerError),
    ],
)
def test_with_pythonic_errors(grpc_status: StatusCode, exception_type: type[E]) -> None:
    # we use the aio error here since it's easier to mock, and it doesn't matter for the test
    grpc_error = AioRpcError(grpc_status, Metadata(), Metadata())

    class Stub:
        def __init__(self) -> None:
            def _mock_rpc() -> None:
                raise grpc_error

            self.some_rpc = _mock_rpc

    stub = with_pythonic_errors(Stub())
    with pytest.raises(exception_type, match=r".*"):
        stub.some_rpc()


@pytest.mark.parametrize("message", ["status: 429", "HTTP 429", "Too Many Requests"])
def test_translate_connect_unavailable_429(message: str) -> None:
    from connectrpc.code import Code  # noqa: PLC0415

    class Error:
        code = Code.UNAVAILABLE

        def __init__(self, message: str) -> None:
            self.message = message

    assert isinstance(translate_connect_error(Error(message)), TooManyRequestsError)
