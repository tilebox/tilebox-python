"""Deferred decoding of nested protobuf fields in query results."""

from collections.abc import Callable
from contextlib import suppress
from typing import Generic, TypeVar

from protobuf import Message

_MessageT = TypeVar("_MessageT", bound=Message)


class LazyMessage(Generic[_MessageT]):  # noqa: PLW1641 -- mutable messages must remain unhashable
    """An encoded protobuf message, decoded once on :meth:`get`.

    Query results use this wrapper for Assets, Links, Storage, and Authentication.
    An optional ``repr_formatter`` decodes the message to summarize it for display.
    Without a formatter, or on a decoding/formatting ValueError, repr uses ``Type(…)``.
    Each wrapper owns its decoded message. Repeated calls to ``get()`` return the
    same mutable object. Ingestion preserves
    edits to that object, or forwards the original bytes if it has not been decoded.

    Invalid encoded messages raise on ``get()``, not on construction. Sharing a
    wrapper (for example through an xarray shallow copy) also shares its message.
    """

    __slots__ = ("_data", "_message_type", "_repr_formatter", "_value")

    def __init__(
        self,
        message_type: type[_MessageT],
        data: bytes,
        *,
        repr_formatter: Callable[[_MessageT], str] | None = None,
    ) -> None:
        self._message_type = message_type
        self._repr_formatter = repr_formatter
        self._data: bytes | None = data
        self._value: _MessageT | None = None

    @property
    def message_type(self) -> type[_MessageT]:
        """The generated message class, available without decoding."""
        return self._message_type

    def get(self) -> _MessageT:
        """Decode once, release the encoded bytes, and return the mutable message."""
        if self._value is None:
            assert self._data is not None
            self._value = self._message_type.from_binary(self._data)
            self._data = None
        return self._value

    def to_binary(self) -> bytes:
        """Return untouched bytes or serialize the current decoded message."""
        if self._value is not None:
            return self._value.to_binary()
        assert self._data is not None
        return self._data

    def __eq__(self, other: object) -> bool:
        if self is other:
            return True
        if isinstance(other, LazyMessage):
            if self.message_type is not other.message_type:
                return False
            return self.get() == other.get()
        if isinstance(other, self.message_type):
            return self.get() == other
        return NotImplemented

    def __repr__(self) -> str:
        if self._repr_formatter is not None:
            with suppress(ValueError):  # Invalid payloads remain displayable; get() still raises.
                return self._repr_formatter(self.get())
        return f"{self._message_type.__name__}(…)"
