"""Exceptions raised by Tilebox API clients."""

# ruff: noqa: INP001 -- tilebox is shared by multiple distributions


class TileboxError(Exception):
    """Base class for Tilebox service errors."""


class NetworkError(TileboxError, OSError):
    """Communication with the service failed."""


class TooManyRequestsError(NetworkError):
    """The request quota has been exhausted."""


class NetworkTimeoutError(NetworkError, TimeoutError):
    """The request deadline expired."""


class AuthenticationError(TileboxError, OSError):
    """Authentication or authorization failed."""


class ArgumentError(TileboxError, ValueError):
    """The request contains invalid arguments."""


class NotFoundError(TileboxError, KeyError):
    """The requested resource does not exist."""


class SubscriptionLimitExceededError(TileboxError, OSError):
    """The subscription's resource limit was exceeded."""


class InternalServerError(TileboxError, KeyError):
    """The service encountered an unexpected error."""


class InvalidRequestError(TileboxError, OSError):
    """The requested endpoint is unavailable."""


class RequestCanceledError(TileboxError):
    """The remote request was canceled."""
