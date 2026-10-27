"""Translate Connect failures into public Tilebox exceptions."""

from connectrpc.code import Code
from connectrpc.errors import ConnectError

from tilebox.errors import (
    ArgumentError,
    AuthenticationError,
    InternalServerError,
    InvalidRequestError,
    NetworkError,
    NetworkTimeoutError,
    NotFoundError,
    RequestCanceledError,
    SubscriptionLimitExceededError,
    TileboxError,
    TooManyRequestsError,
)


def translate_connect_error(error: ConnectError, method_name: str = "") -> TileboxError:  # noqa: C901, PLR0911, PLR0912
    """Map native Connect status codes to the SDK's public exception types."""
    message = error.message
    public = method_name.startswith("/public/")
    match error.code:
        case Code.NOT_FOUND:
            return NotFoundError(message)
        case Code.INVALID_ARGUMENT:
            return ArgumentError(message)
        case Code.UNAUTHENTICATED:
            return AuthenticationError(f"Unauthenticated: {message}")
        case Code.PERMISSION_DENIED:
            return AuthenticationError(f"Unauthorized: {message}")
        case Code.RESOURCE_EXHAUSTED | Code.UNAVAILABLE:
            if "429" in message or "too many requests" in message.lower():
                text = "Too many requests, try again later."
                if public:
                    text += (
                        " To increase your request quota create a free account at "
                        "https://console.tilebox.com and authenticate with an API Key."
                    )
                return TooManyRequestsError(text)
            if error.code == Code.RESOURCE_EXHAUSTED:
                return SubscriptionLimitExceededError(message)
            return NetworkError(f"network error when requesting {method_name}: {message}" if method_name else message)
        case Code.DEADLINE_EXCEEDED:
            return NetworkTimeoutError(f"Request timed out: {message}")
        case Code.ABORTED:
            return NetworkError(f"Request aborted: {message}")
        case Code.CANCELED:
            return RequestCanceledError(f"Request canceled: {message}")
        case Code.UNIMPLEMENTED:
            if public:
                action = method_name.rsplit("/", maxsplit=1)[-1]
                return AuthenticationError(
                    f"{action} is only available for authenticated users. Please provide a valid API Key "
                    "token in your Client. Create a free account at https://console.tilebox.com"
                )
            return InvalidRequestError(
                f"Requested URL {method_name} not found. Update your Tilebox Python Clients to the latest version."
                if method_name
                else message
            )
        case _:
            return InternalServerError(f"Oops, something went wrong: {message}")
