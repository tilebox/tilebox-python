from typing import TypeVar

import pytest
from grpc import StatusCode
from grpc.aio import AioRpcError
from grpc.aio._metadata import Metadata

from _tilebox.grpc.aio.error import with_pythonic_errors
from _tilebox.grpc.error import ArgumentError, AuthenticationError, InternalServerError, NotFoundError

E = TypeVar("E", bound=BaseException)


@pytest.mark.asyncio
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
async def test_with_pythonic_errors(grpc_status: StatusCode, exception_type: type[E]) -> None:
    # we use the aio error here since it's easier to mock, and it doesn't matter for the test
    grpc_error = AioRpcError(grpc_status, Metadata(), Metadata())

    class Stub:
        def __init__(self) -> None:
            async def _mock_rpc() -> None:
                raise grpc_error

            self.some_rpc = _mock_rpc

    stub = with_pythonic_errors(Stub())
    with pytest.raises(exception_type, match=".*"):
        await stub.some_rpc()
