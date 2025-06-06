"""
This module contains error classes for translating various gRPC server response codes into more pythonic exceptions
"""


class AuthenticationError(IOError):
    """AuthenticationError indicates that a server request failed due to a missing or invalid authentication token"""


class ArgumentError(ValueError):
    """ArgumentError indicates that a server request failed due to missing or invalid arguments"""


class NotFoundError(KeyError):
    """NotFoundError indicates that a given resource was not found on the server side"""


class InternalServerError(KeyError):
    """InternalServerError indicates that an unexpected error happened on the server side"""
