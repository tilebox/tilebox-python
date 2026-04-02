from collections.abc import Iterator
from inspect import isawaitable
from io import BytesIO
from sys import modules
from typing import Any
from unittest import mock as std_mock

import niquests
import niquests.adapters as niquests_adapters
import niquests.exceptions as niquests_exceptions
import niquests.models as niquests_models
import pytest
import requests.compat as requests_compat
from niquests.packages import urllib3

modules["requests"] = niquests
modules["requests.adapters"] = niquests_adapters
modules["requests.models"] = niquests_models
modules["requests.exceptions"] = niquests_exceptions
modules["requests.packages.urllib3"] = urllib3
modules["requests.compat"] = requests_compat

import responses  # noqa: E402


# see https://niquests.readthedocs.io/en/latest/community/extensions.html#responses
class _TransferState:
    def __init__(self) -> None:
        self.data_in_count = 0


class _AsyncRawBody:
    def __init__(self, body: bytes) -> None:
        self._body = BytesIO(body)
        self._fp = _TransferState()

    async def read(self, chunk_size: int = -1, decode_content: bool = True) -> bytes:
        _ = decode_content
        chunk = self._body.read() if chunk_size == -1 else self._body.read(chunk_size)
        self._fp.data_in_count += len(chunk)
        return chunk

    async def close(self) -> None:
        self._body.close()

    def release_conn(self) -> None:
        return None


class NiquestsMock(responses.RequestsMock):
    """Extend responses to patch Niquests' sync and async adapters."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, target="niquests.adapters.HTTPAdapter.send", **kwargs)
        self._patcher_async: Any | None = None

    def unbound_on_async_send(self) -> Any:
        async def send(adapter: Any, request: Any, *args: Any, **kwargs: Any) -> Any:
            if args:
                try:
                    kwargs["stream"] = args[0]
                    kwargs["timeout"] = args[1]
                    kwargs["verify"] = args[2]
                    kwargs["cert"] = args[3]
                    kwargs["proxies"] = args[4]
                except IndexError:
                    pass

            stream = bool(kwargs.get("stream"))
            resp = self._on_request(adapter, request, **kwargs)

            if stream:
                body = getattr(getattr(resp, "raw", None), "read", lambda: getattr(resp, "_content", b""))()
                if isawaitable(body):
                    body = await body
                if body is None or isinstance(body, bool):
                    body = b""
                if isinstance(body, str):
                    body = body.encode()
                resp.__class__ = niquests.AsyncResponse
                resp.raw = _AsyncRawBody(body)
                return resp

            resp.__class__ = niquests.Response
            return resp

        return send

    def unbound_on_send(self) -> Any:
        def send(adapter: Any, request: Any, *args: Any, **kwargs: Any) -> Any:
            if args:
                try:
                    kwargs["stream"] = args[0]
                    kwargs["timeout"] = args[1]
                    kwargs["verify"] = args[2]
                    kwargs["cert"] = args[3]
                    kwargs["proxies"] = args[4]
                except IndexError:
                    pass

            return self._on_request(adapter, request, **kwargs)

        return send

    def start(self) -> None:
        if self._patcher:
            return

        self._patcher = std_mock.patch(target=self.target, new=self.unbound_on_send())
        self._patcher_async = std_mock.patch(
            target=self.target.replace("HTTPAdapter", "AsyncHTTPAdapter"),
            new=self.unbound_on_async_send(),
        )
        self._patcher.start()
        self._patcher_async.start()

    def stop(self, allow_assert: bool = True) -> None:
        if self._patcher:
            self._patcher.stop()
            if self._patcher_async is not None:
                self._patcher_async.stop()
            self._patcher = None
            self._patcher_async = None

        if not self.assert_all_requests_are_fired or not allow_assert:
            return

        not_called = [match for match in self.registered() if match.call_count == 0]
        if not_called:
            raise AssertionError(
                f"Not all requests have been executed {[(match.method, match.url) for match in not_called]!r}"
            )


mock = _default_mock = NiquestsMock(assert_all_requests_are_fired=False)
responses.mock = mock
responses._default_mock = _default_mock
for kw in [
    "activate",
    "add",
    "_add_from_file",
    "add_callback",
    "add_passthru",
    "assert_call_count",
    "calls",
    "delete",
    "DELETE",
    "get",
    "GET",
    "head",
    "HEAD",
    "options",
    "OPTIONS",
    "patch",
    "PATCH",
    "post",
    "POST",
    "put",
    "PUT",
    "registered",
    "remove",
    "replace",
    "reset",
    "response_callback",
    "start",
    "stop",
    "upsert",
]:
    if hasattr(responses, kw):
        setattr(responses, kw, getattr(mock, kw))


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def responses_mock() -> Iterator[responses.RequestsMock]:
    responses.mock.reset()
    responses.mock.start()
    try:
        yield responses.mock
    finally:
        responses.mock.stop()
        responses.mock.reset()
