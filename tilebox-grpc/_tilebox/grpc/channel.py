import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar

from grpc import (
    Channel,
    UnaryUnaryClientInterceptor,
    insecure_channel,
    intercept_channel,
    secure_channel,
    ssl_channel_credentials,
)
from grpc.aio import (
    ClientCallDetails,  # import from aio, since grpc.ClientCallDetails is an empty base class
)

# We don't specify the service field, so the config applies to all services
# See https://github.com/grpc/grpc-proto/blob/master/grpc/service_config/service_config.proto#L50-L52
_SERVICE_CONFIG = {
    "methodConfig": [
        {
            "name": [{"service": ""}],
            "retryPolicy": {
                "maxAttempts": 5,
                "initialBackoff": "0.02s",
                "maxBackoff": "5s",
                "backoffMultiplier": 3,
                "retryableStatusCodes": [
                    "RESOURCE_EXHAUSTED",  # 429 Too Many Requests
                    "UNAVAILABLE",  # 503 Service Unavailable
                ],
            },
        }
    ]
}

CHANNEL_OPTIONS = [
    ("grpc.max_receive_message_length", 512 * 1024 * 1024),  # Max 512 MB
    ("grpc.service_config", json.dumps(_SERVICE_CONFIG)),
]


@dataclass
class ChannelInfo:
    url_without_protocol: str
    use_ssl: bool


def open_channel(url: str, auth_token: str | None = None) -> Channel:
    """Open a sync gRPC channel to the given URL.

    Args:
        url: The URL to open a channel to. Depending on the URL, the channel will be a secure (SSL) or insecure channel.
        auth_token: Authentication token for the channel. If set, an interceptor channel will be created which adds
            the given token as metadata to each request.

    Returns:
        A sync gRPC channel.
    """
    channel_info = parse_channel_info(url)
    interceptors: list[UnaryUnaryClientInterceptor] = []
    if auth_token is not None:
        interceptors = [_AuthMetadataInterceptor(auth_token), *interceptors]  # add auth interceptor as the first one

    return intercept_channel(_open_channel(channel_info), *interceptors)


def _open_channel(channel_info: ChannelInfo) -> Channel:
    if channel_info.use_ssl:
        return secure_channel(channel_info.url_without_protocol, ssl_channel_credentials(), CHANNEL_OPTIONS)
    return insecure_channel(channel_info.url_without_protocol, CHANNEL_OPTIONS)


_URL_SCHEME = re.compile(r"^(https?://)?([^: ]+)(:\d+)?/?$")


def parse_channel_info(url: str) -> ChannelInfo:
    """Parse a given url into a ChannelInfo object that can be used to create a gRPC channel.

    For opening a gRPC channel we need a URL without a protocol (http/https) and a port number as part of the url.

    Unix domain socket should be formatted as unix:path or unix://absolute_path. For example:
        - unix:path/to/socket
        - unix:///absolute/path/to/socket

    Args:
        url: The url to parse.

    Returns:
        A ChannelInfo object that can be used to create a gRPC channel.
    """
    # See https://github.com/grpc/grpc/blob/master/doc/naming.md
    if url.startswith("unix:"):
        return ChannelInfo(url, False)

    # `urllib.parse.urlparse` behaves a bit weird with URLs that don't have a scheme but a port number, so regex it is
    if (match := _URL_SCHEME.match(url)) is None:
        raise ValueError(f"Invalid URL: {url}")
    scheme, netloc, port = match.groups()
    netloc = netloc.rstrip("/")
    use_ssl = True

    if scheme == "http://":  # explicitly set http -> require a port
        if port is None:
            raise ValueError("Explicit port required for insecure HTTP channel")
        use_ssl = False

    if scheme is None and port is not None:  # no scheme, but a port that looks like a dev port -> insecure
        use_ssl = port == ":443"

    if use_ssl:
        return ChannelInfo(netloc + (port or ":443"), True)
    return ChannelInfo(netloc + port, False)


RequestType = TypeVar("RequestType")
ResponseType = TypeVar("ResponseType")


class _AuthMetadataInterceptor(UnaryUnaryClientInterceptor):
    def __init__(self, auth_token: str) -> None:
        """A sync gRPC channel interceptor which adds the authorization token as metadata to every request.

        Args:
            auth_token: The authorization token.
        """
        super().__init__()
        self._auth = ("authorization", f"Bearer {auth_token}")

    def intercept_unary_unary(
        self,
        continuation: Callable[[ClientCallDetails, RequestType], ResponseType],
        client_call_details: ClientCallDetails,
        request: RequestType,
    ) -> ResponseType:
        return continuation(add_metadata(client_call_details, [self._auth]), request)


def add_metadata(
    client_call_details: ClientCallDetails, additional_metadata: list[tuple[str, str]]
) -> ClientCallDetails:
    metadata = [] if client_call_details.metadata is None else list(client_call_details.metadata)
    metadata.extend(additional_metadata)
    return ClientCallDetails(
        client_call_details.method,
        client_call_details.timeout,
        metadata,
        client_call_details.credentials,
        client_call_details.wait_for_ready,
    )
