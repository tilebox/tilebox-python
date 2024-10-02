from collections.abc import Callable
from typing import Any, TypeVar, cast

from _tilebox.grpc.error import AnyRpcError, translate_rpc_error
from grpc import RpcError
from grpc.aio import AioRpcError

Stub = TypeVar("Stub")


def with_pythonic_errors(stub: Stub) -> Stub:
    """
    Wrap an async gRPC stub to translate rpc errors into pythonic exceptions.

    This is done this way instead of an error handling interceptor, because tracebacks are much easier to read when
    they are raised directly at the location of the RPC method call.

    Args:
        stub: The async grpc stub to wrap.

    Returns:
        The stub with the rpc methods wrapped.
    """
    for name, rpc in stub.__dict__.items():
        if callable(rpc):
            setattr(stub, name, _wrap_rpc(rpc))
    return stub


def _wrap_rpc(rpc: Callable[[Any], Any]) -> Callable[[Any], Any]:
    async def call(*args: Any, **kwargs: Any) -> Any:
        try:
            return await rpc(*args, **kwargs)
        except (RpcError, AioRpcError) as err:
            error = translate_rpc_error(cast(AnyRpcError, err))

            # raise the appropriate exception for the error code we received
            raise error from None

    return call
