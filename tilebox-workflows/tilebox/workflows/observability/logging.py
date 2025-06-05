# allow the logging module name which shadows the builtin:
import contextlib
import logging
import os
import re
import sys
import traceback
from datetime import timedelta
from functools import lru_cache
from importlib.metadata import PackageNotFoundError, version
from typing import ClassVar, TextIO
from uuid import uuid4

from opentelemetry.exporter.otlp.proto.http._log_exporter import (
    DEFAULT_LOGS_EXPORT_PATH,
    OTLPLogExporter,
    _append_logs_path,
)
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.resources import SERVICE_INSTANCE_ID, SERVICE_NAME, SERVICE_VERSION, Resource
from opentelemetry.semconv.attributes import exception_attributes
from opentelemetry.util.types import _ExtendedAttributes

# prefix for stdlib loggers
_LOGGING_NAMESPACE = "tilebox.workflows"

_AXIOM_ENDPOINT = "https://api.axiom.co/v1/logs"
_AXIOM_LOGS_DATASET_ENV_VAR = "AXIOM_LOGS_DATASET"
_AXIOM_API_KEY_ENV_VAR = "AXIOM_API_KEY"

_OTEL_LOGS_ENDPOINT_ENV_VAR = "OTEL_LOGS_ENDPOINT"
_OTEL_EXPORT_INTERVAL_ENV_VAR = "OTEL_EXPORT_INTERVAL"


def _get_default_resource(service: str | Resource | None = None) -> Resource:
    if isinstance(service, Resource):  # already a resource object, no need to create a default one
        return service

    service_name = service if isinstance(service, str) else f"tilebox.workflows-{os.getpid()}"

    instance_id = f"{os.uname().nodename}-{os.getpid()}"
    workflows_version = "dev"
    with contextlib.suppress(PackageNotFoundError):
        workflows_version = version("tilebox-workflows")
    return Resource.create(
        attributes={
            SERVICE_NAME: service_name,
            SERVICE_INSTANCE_ID: instance_id,
            SERVICE_VERSION: workflows_version,
        }
    )


@lru_cache
def _root_logger() -> logging.Logger:
    root_logger = logging.getLogger(_LOGGING_NAMESPACE)
    # our root logger needs DEBUG level, otherwise it would always automatically
    # discard all DEBUG messages and never forward them to any handler, even if they
    # have a DEBUG level set
    root_logger.setLevel(logging.DEBUG)
    return root_logger


class OTELLoggingHandler(LoggingHandler):
    @staticmethod
    def _get_attributes(record: logging.LogRecord) -> _ExtendedAttributes:
        attributes = {}
        # the default implementation returns attributes for the filepath, lineno and function of the log record
        # we don't want that by default, so we override it to return an empty dict
        if record.exc_info:
            exctype, value, tb = record.exc_info
            if exctype is not None:
                attributes[exception_attributes.EXCEPTION_TYPE] = exctype.__name__
            if value is not None and value.args:
                attributes[exception_attributes.EXCEPTION_MESSAGE] = value.args[0]
            if tb is not None:
                # https://github.com/open-telemetry/opentelemetry-specification/blob/9fa7c656b26647b27e485a6af7e38dc716eba98a/specification/trace/semantic_conventions/exceptions.md#stacktrace-representation
                attributes[exception_attributes.EXCEPTION_STACKTRACE] = "".join(
                    traceback.format_exception(*record.exc_info)
                )
        return attributes


def _otel_handler(
    level: int = logging.NOTSET,
    service: str | Resource | None = None,
    endpoint: str | None = None,
    headers: dict[str, str] | None = None,
    export_interval: timedelta | None = None,
) -> LoggingHandler:
    resource = _get_default_resource(service)
    logger_provider = LoggerProvider(resource)

    if endpoint is None:
        endpoint = os.environ.get(_OTEL_LOGS_ENDPOINT_ENV_VAR, None)
    if endpoint is None:
        raise ValueError(
            f"No OTEL logs endpoint provided and no {_OTEL_LOGS_ENDPOINT_ENV_VAR} environment variable set. Please "
            f"specify an endpoint using the endpoint argument or the environment variable."
        )

    if not endpoint.endswith(DEFAULT_LOGS_EXPORT_PATH):
        endpoint = _append_logs_path(endpoint)

    if export_interval is None:
        export_interval_env = os.environ.get(_OTEL_EXPORT_INTERVAL_ENV_VAR, None)
        if export_interval_env is not None:
            export_interval = _parse_duration(export_interval_env)
    # it's fine if it is none, we will just use the opentelemetry default

    exporter = OTLPLogExporter(
        endpoint=endpoint,
        headers=headers,
    )
    schedule_delay = int(export_interval.total_seconds() * 1000) if export_interval is not None else None
    batch_exporter = BatchLogRecordProcessor(exporter, schedule_delay_millis=schedule_delay)  # type: ignore[arg-type]

    logger_provider.add_log_record_processor(batch_exporter)
    return OTELLoggingHandler(level=level, logger_provider=logger_provider)


def configure_otel_logging(  # noqa: PLR0913
    service: str | Resource | None = None,
    level: int = logging.DEBUG,
    endpoint: str | None = None,
    headers: dict[str, str] | None = None,
    export_interval: timedelta | None = None,
    reconfigure: bool = True,
) -> None:
    """
    Configure logging to an OTLP compatible endpoint.

    This will configure a logging handler that will send log messages to an OTLP compatible endpoint using the
    open telemetry protocol for exporting logs. The logging handler will be attached to the root tilebox logger.
    All loggers created using `get_logger()` will therefore inherit this handler configuration.

    Args:
        service: A string or a resource object to include in all traces. Used to identify the service being traced.
            If a string is provided, it will be used as the service name. If a resource object is provided, it will be
            used as the resource. Defaults to a resource with the service name set to "tilebox.workflows-{process_id}",
            the version set to the version of the package, and the service instance id set to a combination
            of hostname and process id.
        level: The logging level to use for the OTEL handler. Only log messages with a level higher or equal to
            this will be sent to the endpoint. Defaults to logging.DEBUG. It is typically recommended to keep this at a
            lower level, since actual filtering of log messages to higher levels is typically done by the logger itself.
            See the level argument of `get_logger()` for more information.
        endpoint: The URL of the OTLP compatible endpoint to send logs to. If not provided, the environment
            variable OTEL_LOGS_ENDPOINT will be used. If that is not set either, an error will be raised.
            OTLP compatible endpoints typically have the path name "/v1/logs". If the specified endpoint does not
            include this path, it will be added automatically.
        headers: A dictionary of HTTP headers to include into each request to the endpoint.
        export_interval: The interval at which to export logs to the endpoint. If not provided, the
            environment variable OTEL_EXPORT_INTERVAL will be used. If that is not set either, the default open
            telemetry export interval of 5s will be used.
        reconfigure: Only relevant if configure_otel_logging is called multiple times. If True, any previously
            configured OTEL logging handlers will be removed. If False, the existing handlers will be kept. Useful
            if you want to log to multiple OTEL endpoints.

    Raises:
        ValueError: If no endpoint is provided and no OTEL_LOGS_ENDPOINT environment variable is set.
    """
    handler = _otel_handler(level, service, endpoint, headers, export_interval)
    root_logger = _root_logger()

    # clean up previous handlers:
    # remove the default handler if it exists, and all other OtelHandlers if reconfigure is True
    handlers_to_remove_indices = [
        i
        for i, handler in enumerate(root_logger.handlers)
        if hasattr(handler, "_is_default") or (reconfigure and isinstance(handler, OTELLoggingHandler))
    ]
    for i in reversed(handlers_to_remove_indices):  # reversed to avoid index shifting after deletion
        root_logger.handlers.pop(i)

    root_logger.addHandler(handler)


def configure_otel_logging_axiom(
    service: str | Resource | None = None,
    level: int = logging.DEBUG,
    dataset: str | None = None,
    api_key: str | None = None,
    reconfigure: bool = True,
) -> None:
    """
    Configure opentelemetry logging to Axiom.

    This will configure a logging handler that will send log messages to Axiom. The logging handler will be attached
    to the root tilebox logger. All loggers created using `get_logger()` will therefore inherit this handler
    configuration.

    Args:
        service: A string or a resource object to include in all traces. Used to identify the service being traced.
            If a string is provided, it will be used as the service name. If a resource object is provided, it will be
            used as the resource. Defaults to a resource with the service name set to "tilebox.workflows-{process_id}",
            the version set to the version of the package, and the service instance id set to a combination
            of hostname and process id.
        level: The logging level to use for the Axiom log handler. Only log messages with a level higher or equal to
            this will be sent to the endpoint. Defaults to logging.DEBUG. It is typically recommended to keep this at a
            lower level, since actual filtering of log messages to higher levels is typically done by the logger itself.
            See the level argument of `get_logger()` for more information.
        dataset: The name of the Axiom dataset to ingest logs into. If not provided, the environment variable
            AXIOM_LOGS_DATASET will be used. If that is not set either, an error will be raised.
        api_key: The API key to use for authentication. If not provided, the environment variable AXIOM_API_KEY will be
            used. If that is not set either, an error will be raised.
        reconfigure: Only relevant if configure_otel_logging_axiom is called multiple times. If True, any previously
            configured OTEL logging handlers will be removed. If False, the existing handlers will be kept. Useful
            if you want to log to multiple OTEL endpoints.

    Raises:
        ValueError: If no dataset is provided and no AXIOM_LOGS_DATASET environment variable is set
            or no API key is provided and no AXIOM_API_KEY environment variable is set.
    """
    if dataset is None:
        dataset = os.environ.get(_AXIOM_LOGS_DATASET_ENV_VAR, None)
    if api_key is None:
        api_key = os.environ.get(_AXIOM_API_KEY_ENV_VAR, None)

    if dataset is None:
        raise ValueError(
            f"No Axiom logs dataset provided and no {_AXIOM_LOGS_DATASET_ENV_VAR} environment variable set. Please "
            f"specify a dataset using the dataset argument or the environment variable."
        )
    if api_key is None:
        raise ValueError(
            f"No Axiom API Key provided and no {_AXIOM_API_KEY_ENV_VAR} environment variable set. Please "
            f"specify a dataset using the api_key argument or the environment variable."
        )

    configure_otel_logging(
        service,
        level,
        endpoint=_AXIOM_ENDPOINT,
        headers={"Authorization": f"Bearer {api_key}", "X-Axiom-Dataset": dataset},
        reconfigure=reconfigure,
    )


class ColorfulConsoleFormatter(logging.Formatter):
    """A logging formatter that adds colors to the console output, depending on the log level."""

    reset = "\033[0m"
    faint = "\033[38;5;241m"
    bright_red = "\033[31m"
    bright_green = "\033[92m"
    bright_yellow = "\033[93m"
    bright_red_faint = "\033[91;2m"

    FORMATS: ClassVar[dict[int, str]] = {
        logging.DEBUG: faint + "%(asctime)s %(levelname)s %(message)s" + reset,
        logging.INFO: faint + "%(asctime)s" + reset + bright_green + " %(levelname)s " + reset + "%(message)s",
        logging.WARNING: faint + "%(asctime)s" + reset + bright_yellow + " %(levelname)s " + reset + "%(message)s",
        logging.ERROR: faint + "%(asctime)s" + reset + bright_red_faint + " %(levelname)s " + reset + "%(message)s",
        logging.CRITICAL: bright_red + "%(asctime)s %(levelname)s %(message)s" + reset,
    }

    def format(self, record: logging.LogRecord) -> str:
        log_fmt = self.FORMATS.get(record.levelno, "%(asctime)s %(levelname)s %(message)s")
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


def configure_console_logging(
    level: int = logging.INFO, stream: TextIO | None = None, reconfigure: bool = True
) -> None:
    """
    Configure logging to the console (stdout).

    This will configure a logging handler that will send log messages to the console. The logging handler will be
    attached to the root tilebox logger. All loggers created using `get_logger()` will therefore inherit this handler
    configuration.

    Args:
        level: The logging level to use for the console handler. Only log messages with a level higher or equal to
            this will be sent to the console. Defaults to logging.INFO.
        stream: The TextIO stream to use as output for logging. Defaults to sys.stdout.
        reconfigure: Only relevant if configure_console_logging is called multiple times. If True, any previously
            configured console logging handlers will be removed. If False, the existing handlers will be kept. Useful
            if you want to log to multiple consoles.
    """
    if stream is None:
        stream = sys.stdout

    handler = logging.StreamHandler(stream)
    handler.setLevel(level)
    handler.setFormatter(ColorfulConsoleFormatter())

    root_logger = _root_logger()

    # clean up previous handlers:
    # remove the default handler if it exists, and all other ConsoleHandlers if reconfigure is True
    handlers_to_remove_indices = [
        i
        for i, handler in enumerate(root_logger.handlers)
        if hasattr(handler, "_is_default")
        or (
            reconfigure
            and isinstance(handler, logging.StreamHandler)
            and isinstance(handler.formatter, ColorfulConsoleFormatter)
        )
    ]
    for i in reversed(handlers_to_remove_indices):  # reversed to avoid index shifting after deletion
        root_logger.handlers.pop(i)

    root_logger.addHandler(handler)


def get_logger(name: str | None = None, level: int = logging.NOTSET) -> logging.Logger:
    """
    Get a logger with a given name and level.

    Loggers created using this function will inherit the configuration of the root tilebox logger, which can be
    configured using the `configure_console_logging()`, `configure_otel_logging()` or `configure_otel_logging_axiom()`
    functions.

    Args:
        name: A optional name for the logger. Can be used to define custom logging handlers that filter, modify or
            handle log messages from specific loggers. If not provided, a random name will be generated.
            This random name prevents overriding log levels of other loggers returned by `get_logger()` without
            explicitly specifying a name.
        level: The logging level to use for the logger. Only log messages with a level higher or equal to this will be
            sent to the logger. Only log messages with a level higher or equal to this will be sent by the logger to
            configured handlers. Defaults to logging.NOTSET, which effectively means all messages will be forwarded
            to the handlers.

    Returns:
        A logger capable of logging messages that will be sent to the configured handlers.
    """
    if name is None:
        name = f"unnamed_logger_{uuid4()}"

    root_logger = _root_logger()
    if not root_logger.hasHandlers():
        # no handlers are configured, so we add a standard console handler
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)
        handler.setFormatter(ColorfulConsoleFormatter())
        # we set a special attribute, which allows as to remove this handler again as soon
        # as we configure an actual logging handler
        handler._is_default = True  # type: ignore[attr-defined] # noqa: SLF001
        root_logger.addHandler(handler)

    logger = logging.getLogger(f"{_LOGGING_NAMESPACE}.{name}")
    logger.setLevel(level)
    return logger


_DURATION_REGEX = re.compile(
    r"^((?P<days>[\.\d]+?)d)?((?P<hours>[\.\d]+?)h)?((?P<minutes>[\.\d]+?)m)?((?P<seconds>[\.\d]+?)s)?$"
)


def _parse_duration(time_str: str) -> timedelta:
    """
    Parse a time string e.g. (2h13m) into a timedelta object.

    Modified from virhilo's answer at https://stackoverflow.com/a/4628148/851699

    Args:
        time_str: A string identifying a duration.  (eg. 2h13m)

    Returns:
        datetime.timedelta: A datetime.timedelta object
    """
    parts = _DURATION_REGEX.match(time_str)
    if parts is None:
        raise ValueError(
            f"Could not parse any duration from '{time_str}'.  Examples of valid strings: '8h', '2d8h5m20s', '2m4s'"
        )

    time_params = {name: float(param) for name, param in parts.groupdict().items() if param}
    return timedelta(**time_params)
