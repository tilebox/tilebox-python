from collections.abc import Callable
from typing import TypeVar

from _tilebox.grpc.channel import CHANNEL_OPTIONS, ChannelInfo, add_metadata, parse_channel_info
from grpc import ssl_channel_credentials
from grpc.aio import (
    Channel,
    ClientCallDetails,
    UnaryUnaryCall,
    insecure_channel,
    secure_channel,
)
from grpc.aio._interceptor import UnaryUnaryClientInterceptor


def open_channel(url: str, auth_token: str | None = None) -> Channel:
    """Open an async gRPC channel to the given URL.

    Args:
        url: The URL to open a channel to. Depending on the URL, the channel will be a secure (SSL) or insecure channel.
        auth_token: Authentication token for the channel. If set, an interceptor channel will be created which adds
            the given token as metadata to each request.

    Returns:
        A gRPC channel.
    """
    channel_info = parse_channel_info(url)
    interceptors: list[UnaryUnaryClientInterceptor] = []
    if auth_token is not None:
        interceptors = [_AuthMetadataInterceptor(auth_token), *interceptors]  # add auth interceptor as the first one

    return _open_channel(channel_info, interceptors)


def _open_channel(channel_info: ChannelInfo, interceptors: list[UnaryUnaryClientInterceptor]) -> Channel:
    if channel_info.use_ssl:
        return secure_channel(
            channel_info.url_without_protocol, ssl_channel_credentials(), CHANNEL_OPTIONS, interceptors=interceptors
        )
    return insecure_channel(channel_info.url_without_protocol, CHANNEL_OPTIONS, interceptors=interceptors)


RequestType = TypeVar("RequestType")


class _AuthMetadataInterceptor(UnaryUnaryClientInterceptor):
    def __init__(self, auth_token: str) -> None:
        """A gRPC channel interceptor which adds the authorization token as metadata to every request.

        Args:
            auth_token: The authorization token.
        """
        super().__init__()
        self._auth = ("authorization", f"Bearer {auth_token}")

    async def intercept_unary_unary(
        self,
        continuation: Callable[[ClientCallDetails, RequestType], UnaryUnaryCall],
        client_call_details: ClientCallDetails,
        request: RequestType,
    ) -> UnaryUnaryCall:
        return await continuation(add_metadata(client_call_details, [self._auth]), request)
