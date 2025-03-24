"""
This module contains error classes for translating various gRPC server response codes into more pythonic exceptions
"""

from collections.abc import Callable, Coroutine
from typing import Any, Protocol, TypeVar, cast

from grpc import RpcError, StatusCode
from grpc.aio import AioRpcError


class AuthenticationError(IOError):
    """AuthenticationError indicates that a server request failed due to a missing or invalid authentication token"""


class ArgumentError(ValueError):
    """ArgumentError indicates that a server request failed due to missing or invalid arguments"""


class NotFoundError(KeyError):
    """NotFoundError indicates that a given resource was not found on the server side"""


class SubscriptionLimitExceededError(IOError):
    """SubscriptionLimitExceededError indicates that the subscription limit for a resource has been reached"""


class InternalServerError(KeyError):
    """InternalServerError indicates that an unexpected error happened on the server side"""


Stub = TypeVar("Stub")


def with_pythonic_errors(stub: Stub, async_funcs: bool = False) -> Stub:
    """
    Wrap a sync gRPC stub to translate rpc errors into pythonic exceptions.

    This is done this way instead of an error handling interceptor, because tracebacks are much easier to read when
    they are raised directly at the location of the RPC method call.

    Args:
        stub: The grpc stub to wrap.
        async_funcs: Whether to wrap the callables as coroutines or not. Defaults to False.

    Returns:
        The stub with the rpc methods wrapped.
    """
    wrap_func = _wrap_rpc if not async_funcs else _async_wrap_rpc
    for name, rpc in stub.__dict__.items():
        if callable(rpc):
            setattr(stub, name, wrap_func(rpc))  # type: ignore[assignment]
    return stub


class AnyRpcError(Protocol):
    """Protocol for gRPC errors that works for both sync and async gRPC."""

    def code(self) -> StatusCode: ...
    def details(self) -> str: ...


def translate_rpc_error(err: AnyRpcError) -> Exception:
    # translate specific error codes to more pythonic errors
    match err.code():
        case StatusCode.UNAUTHENTICATED:
            return AuthenticationError(f"Unauthenticated: {err.details()}")
        case StatusCode.PERMISSION_DENIED:
            return AuthenticationError(f"Unauthorized: {err.details()}")
        case StatusCode.NOT_FOUND:
            return NotFoundError(err.details())
        case StatusCode.RESOURCE_EXHAUSTED:
            return SubscriptionLimitExceededError(err.details())
        case StatusCode.INVALID_ARGUMENT:
            return ArgumentError(err.details())

    return InternalServerError(f"Oops, something went wrong: {err.details()}")


def _wrap_rpc(rpc: Callable[[Any], Any]) -> Callable[[Any], Any]:
    def call(*args: Any, **kwargs: Any) -> Any:
        try:
            return rpc(*args, **kwargs)
        except (RpcError, AioRpcError) as err:
            error = translate_rpc_error(cast(AnyRpcError, err))

            # raise the appropriate exception for the error code we received
            raise error from None

    return call


def _async_wrap_rpc(rpc: Callable[[Any], Coroutine[Any, Any, Any]]) -> Callable[[Any], Coroutine[Any, Any, Any]]:
    async def call(*args: Any, **kwargs: Any) -> Any:
        try:
            return await rpc(*args, **kwargs)
        except (RpcError, AioRpcError) as err:
            error = translate_rpc_error(cast(AnyRpcError, err))

            # raise the appropriate exception for the error code we received
            raise error from None

    return call
