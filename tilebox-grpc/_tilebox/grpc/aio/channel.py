from collections.abc import Callable, Sequence
from typing import TypeVar

from _tilebox.grpc.channel import CHANNEL_OPTIONS, ChannelInfo, ChannelProtocol, add_metadata, parse_channel_info
from grpc import Compression, ssl_channel_credentials
from grpc.aio import (
    Channel,
    ClientCallDetails,
    ClientInterceptor,
    UnaryUnaryCall,
    UnaryUnaryClientInterceptor,
    insecure_channel,
    secure_channel,
)


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
    interceptors: list[ClientInterceptor] = []
    if auth_token is not None:
        interceptors = [_AuthMetadataInterceptor(auth_token), *interceptors]  # add auth interceptor as the first one

    return _open_channel(channel_info, interceptors)


def _open_channel(channel_info: ChannelInfo, interceptors: Sequence[ClientInterceptor]) -> Channel:
    match channel_info.protocol:
        case ChannelProtocol.HTTPS:
            return secure_channel(
                f"{channel_info.address}:{channel_info.port}",
                ssl_channel_credentials(),
                CHANNEL_OPTIONS,
                compression=Compression.Gzip,
                interceptors=interceptors,
            )
        case ChannelProtocol.HTTP:
            return insecure_channel(
                f"{channel_info.address}:{channel_info.port}",
                CHANNEL_OPTIONS,
                compression=Compression.NoCompression,
                interceptors=interceptors,
            )
        case ChannelProtocol.UNIX:
            return insecure_channel(
                channel_info.address, CHANNEL_OPTIONS, compression=Compression.NoCompression, interceptors=interceptors
            )
        case _:
            raise ValueError(f"Unsupported channel protocol: {channel_info.protocol}")


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
