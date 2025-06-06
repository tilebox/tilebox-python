"""
This module provides a mixin class Syncifiable that can be used to add a _syncify() method to a class which when called
patches an object and replaces all async functions in the object to be blocking sync functions instead.

For all async operations in the codebase we use the anyio library, which allows the library to be used with both
the asyncio and the trio (a third party async library) event loop. However, here we must decide on one event loop
since we need to run it directly for syncifying async functions. We use asyncio, since it is part of the standard
library
"""

import asyncio
import functools
import inspect
from collections.abc import Callable
from typing import Any, TypeVar

import nest_asyncio

# this is a patch to enable syncify functionality also inside a running event loop, which is e.g. the case when
# running in a Jupyter notebook or in a pytest session. In that case we need to use nest_asyncio to allow
# running nested event loops.
nest_asyncio.apply()


class Syncifiable:
    """
    A mixin that provides a _syncify method which can be used to wrap all async functions in a blocking sync function.
    """

    def _syncify(self) -> None:
        return syncify(self)


T_Syncifiable = TypeVar("T_Syncifiable", bound=Syncifiable)


def syncify(instance: Any) -> None:
    """
    Patch all public async functions and generators in the given instance to be blocking sync functions instead.

    One known limitation of this approach is that it breaks return type inference for the patched functions.
    A possible way to get around this could be to use metaprogramming to create a new class with the patched functions
    on the fly and hope the type checker can infer that.

    Args:
        instance: The instance to patch
    """
    for name in dir(instance):
        if name.startswith("_"):
            continue
        attr = getattr(instance, name)
        if inspect.iscoroutinefunction(attr):  # standard async function / coroutine
            setattr(instance, name, _syncify_coroutine(attr))
        elif inspect.isasyncgenfunction(attr):  # async generator
            setattr(instance, name, _syncify_async_generator(attr))


def _syncify_coroutine(coroutine: Callable[..., Any]) -> Callable[..., Any]:
    """Wrap a coroutine function to be a blocking sync function.

    Args:
        coroutine: The coroutine to wrap

    Returns:
        Callable: The wrapped coroutine as a blocking sync function.
    """

    @functools.wraps(coroutine)  # preserve name, docstring, signature etc. of the original function
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        return asyncio.run(coroutine(*args, **kwargs))

    return wrapper


def _syncify_async_generator(async_generator: Callable[..., Any]) -> Callable[..., Any]:
    """Wrap an async generator to be a blocking sync generator.

    This requires a bit more work than wrapping a coroutine function, because we need a coroutine helper function that
    waits for the next value in the async generator and returns it. This helper function is then wrapped in a blocking
    sync generator. This is necessary because even in the sync generator we want to yield the values as they come in
    and not wait for the entire async generator to complete before yielding the values.

    Args:
        async_generator: The async generator to wrap

    Yields:
        Iterator: Generator over the yielded values of the async generator.
    """

    # inspired by https://stackoverflow.com/a/63595496
    @functools.wraps(async_generator)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        async_iter = async_generator(*args, **kwargs).__aiter__()

        async def _next() -> tuple[bool, Any]:
            try:
                obj = await async_iter.__anext__()
            except StopAsyncIteration:
                return True, None
            return False, obj

        while True:
            done, obj = asyncio.run(_next())
            if done:
                break
            yield obj

    return wrapper
