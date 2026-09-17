# allow the logging module name which shadows the builtin:
import atexit
import contextlib
import logging
import os
import platform
import re
import sys
import threading
import traceback
from datetime import timedelta
from importlib.metadata import PackageNotFoundError, version
from typing import Any, ClassVar, TextIO
from uuid import UUID, uuid4

import msgspec
from opentelemetry.exporter.otlp.proto.http._log_exporter import (
    DEFAULT_LOGS_EXPORT_PATH,
    OTLPLogExporter,
    _append_logs_path,
)
from opentelemetry.instrumentation.logging.handler import LoggingHandler
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.resources import (
    HOST_ARCH,
    HOST_NAME,
    OS_TYPE,
    PROCESS_PID,
    SERVICE_INSTANCE_ID,
    SERVICE_NAME,
    SERVICE_NAMESPACE,
    SERVICE_VERSION,
    Resource,
)
from opentelemetry.semconv.attributes import exception_attributes
from opentelemetry.util.types import _ExtendedAttributes

from tilebox.workflows._serialization import normalize_log_value
from tilebox.workflows.observability._log_pipe import _PipeWriter, _StructuredHandler
from tilebox.workflows.observability._logging import (
    StructuredLogger as StructuredLogger,  # noqa: PLC0414 -- public compatibility alias
)
from tilebox.workflows.observability._logging import (
    _record_attributes,
    internal_logger,
    root_logger,
    task_logger,
)

# prefix for stdlib loggers
_DEFAULT_SERVICE_NAME = "tilebox-python"

_AXIOM_ENDPOINT = "https://api.axiom.co/v1/logs"
_AXIOM_LOGS_DATASET_ENV_VAR = "AXIOM_LOGS_DATASET"
_AXIOM_API_KEY_ENV_VAR = "AXIOM_API_KEY"

_OTEL_LOGS_ENDPOINT_ENV_VAR = "OTEL_LOGS_ENDPOINT"
_OTEL_EXPORT_INTERVAL_ENV_VAR = "OTEL_EXPORT_INTERVAL"

# Use the CLI's runtime identity, or generate one per process for direct runners.
_instance_id = os.environ.get("TILEBOX_RUNTIME_ID") or str(uuid4())
_instance_id = str(UUID(_instance_id))


def _get_default_resource(service: str | Resource | None = None) -> Resource:
    if isinstance(service, Resource):  # already a resource object
        service_name = service.attributes.get(SERVICE_NAME)
        if service_name is not None and service_name != "unknown_service":
            # default value of SERVICE_NAME is "unknown_service", so if we have anything other than that we
            # know it's already configured
            return service

    service_name = service if isinstance(service, str) else _DEFAULT_SERVICE_NAME

    workflows_version = "dev"
    with contextlib.suppress(PackageNotFoundError):
        workflows_version = version("tilebox-workflows")

    uname = platform.uname()
    return Resource.create(
        attributes={
            SERVICE_NAMESPACE: "tilebox.workflows",
            SERVICE_NAME: service_name,
            SERVICE_INSTANCE_ID: _instance_id,
            SERVICE_VERSION: workflows_version,
            PROCESS_PID: os.getpid(),
            HOST_NAME: uname.node,
            HOST_ARCH: uname.machine.lower(),
            OS_TYPE: uname.system.lower(),
        }
    )


def _sanitize_otel_attribute_value(
    value: Any,
) -> str | bool | int | float | bytes | list[str | bool | int | float | bytes]:
    if isinstance(value, str | bool | int | float | bytes):
        return value

    if isinstance(value, list):
        return [
            item if isinstance(item, str | bool | int | float) else msgspec.json.encode(item).decode() for item in value
        ]
    # OTEL span attributes cannot contain mappings; retain their JSON representation.
    return msgspec.json.encode(value).decode()


def _sanitize_otel_attributes(attributes: dict[str, Any]) -> dict[str, Any]:
    return {str(key): _sanitize_otel_attribute_value(value) for key, value in attributes.items()}


class OTELLoggingHandler(LoggingHandler):
    def _get_attributes(self, record: logging.LogRecord) -> _ExtendedAttributes:
        cached = getattr(record, "_tilebox_otel_attributes", None)
        if cached is not None:
            return cached
        attributes = _sanitize_otel_attributes(_record_attributes(record))

        # the default implementation returns attributes for the filepath, lineno and function of the log record
        # we don't want that by default, so we override it to return an empty dict
        if record.exc_info:
            exctype, value, tb = record.exc_info
            if exctype is not None:
                attributes[exception_attributes.EXCEPTION_TYPE] = exctype.__name__
            if value is not None and value.args:
                attributes[exception_attributes.EXCEPTION_MESSAGE] = _sanitize_otel_attribute_value(
                    normalize_log_value(value.args[0])
                )
            if tb is not None:
                # https://github.com/open-telemetry/opentelemetry-specification/blob/9fa7c656b26647b27e485a6af7e38dc716eba98a/specification/trace/semantic_conventions/exceptions.md#stacktrace-representation
                attributes[exception_attributes.EXCEPTION_STACKTRACE] = "".join(
                    traceback.format_exception(*record.exc_info)
                )
        record._tilebox_otel_attributes = attributes  # noqa: SLF001 -- shared across OTEL handlers for this record
        return attributes


_api_handler: OTELLoggingHandler | None = None
_initialization_lock = threading.Lock()
_writer: _PipeWriter | None = None
_console_handlers: list[logging.Handler] = []
_console_configured = False


def _remove_console_handlers() -> None:
    for handler in _console_handlers:
        root_logger.removeHandler(handler)
        handler.close()
    _console_handlers.clear()


def _add_console_handler(level: int, stream: TextIO, formatter: logging.Formatter) -> None:
    handler = logging.StreamHandler(stream)
    handler.setLevel(level)
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)
    _console_handlers.append(handler)


def _configure_runtime_logging() -> _PipeWriter | None:
    """Install the required CLI pipe, or an optional default console for direct runners.

    The CLI pipe is runtime-owned: public configuration can add outputs but cannot
    disable or replace it. Console opt-out applies only to console handlers.
    """
    global _writer  # noqa: PLW0603 -- process-owned CLI pipe
    with _initialization_lock:
        fd_value = os.environ.get("TILEBOX_LOG_FD")
        if fd_value is not None:
            if _writer is None:
                _writer = _PipeWriter(int(fd_value))
                root_logger.addHandler(_StructuredHandler(_writer))
                atexit.register(_writer.close)
            if not _console_configured:
                _remove_console_handlers()
        elif not _console_configured and not _console_handlers:
            _add_console_handler(
                logging.NOTSET, sys.stdout, logging.Formatter("%(process)d: %(levelname)s: %(message)s")
            )
        return _writer


def configure_log_level(level: int = logging.INFO, *, tilebox_debug: bool = False) -> None:
    """Override process-wide task and Tilebox diagnostic levels without changing outputs.

    Startup uses TILEBOX_LOG_LEVEL (INFO by default) and TILEBOX_DEBUG (false by default),
    normally supplied by the CLI. This override is useful for direct Python runners or
    notebooks, for example to enable task DEBUG messages without changing environment
    variables. Lowering a handler's threshold alone cannot recover messages already
    filtered out by the logger.

    Every call overrides both startup settings: omitting tilebox_debug disables internal
    DEBUG logging even if TILEBOX_DEBUG was enabled. Existing API exports, the CLI pipe,
    and console handlers are unchanged and retain their own output thresholds.

    Args:
        level: Task log threshold, including context.logger. Defaults to logging.INFO.
        tilebox_debug: Enable internal Tilebox diagnostics at DEBUG when True; otherwise
            use ERROR. Defaults to False, independently of the task log level.
    """
    task_logger.setLevel(level)
    internal_logger.setLevel(logging.DEBUG if tilebox_debug else logging.ERROR)


def initialize_logging(url: str, token: str | None, service: str | None = None) -> None:
    """Initialize process-wide API and local logging once; the first destination wins.

    Both loggers propagate to one API handler at NOTSET. Thresholds belong to the
    loggers, so every accepted record is exported regardless of its source.
    """
    global _api_handler  # noqa: PLW0603 -- process-wide initialization shared by all startup paths
    _configure_runtime_logging()
    with _initialization_lock:
        if _api_handler is not None:
            return

        provider = LoggerProvider(resource=_get_default_resource(service))
        processor = _otel_log_exporter(endpoint=url, headers={"Authorization": f"Bearer {token}"} if token else None)
        provider.add_log_record_processor(processor)
        handler = OTELLoggingHandler(level=logging.NOTSET, logger_provider=provider)
        root_logger.addHandler(handler)
        _api_handler = handler


def _otel_log_exporter(
    endpoint: str | None = None,
    headers: dict[str, str] | None = None,
    export_interval: timedelta | None = None,
) -> BatchLogRecordProcessor:
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
    return BatchLogRecordProcessor(exporter, schedule_delay_millis=schedule_delay)


def configure_otel_logging(
    service: str | Resource | None = None,
    level: int = logging.DEBUG,
    endpoint: str | None = None,
    headers: dict[str, str] | None = None,
    export_interval: timedelta | None = None,
) -> None:
    """
    Configure logging to an OTLP compatible endpoint.

    This will configure a logging handler that will send log messages to an OTLP compatible endpoint using the
    open telemetry protocol for exporting logs. The logging handler will be attached to the root tilebox logger.
    All loggers created using `get_logger()` will therefore inherit this handler configuration.
    Each call adds an export; Tilebox's API export, the CLI pipe, and console outputs remain installed.

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

    Raises:
        ValueError: If no endpoint is provided and no OTEL_LOGS_ENDPOINT environment variable is set.
    """
    provider = LoggerProvider(resource=_get_default_resource(service))

    batch_exporter = _otel_log_exporter(endpoint, headers, export_interval)
    provider.add_log_record_processor(batch_exporter)
    handler = OTELLoggingHandler(level=level, logger_provider=provider)

    root_logger.addHandler(handler)


def configure_otel_logging_axiom(
    service: str | Resource | None = None,
    level: int = logging.DEBUG,
    dataset: str | None = None,
    api_key: str | None = None,
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
    level: int = logging.INFO, stream: TextIO | None = None, reconfigure: bool = True, *, enabled: bool = True
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
        enabled: If False, remove Tilebox-managed console handlers and disable automatic console output, even if
            called before runner startup. API exports, the CLI log pipe, and user-installed handlers are unaffected.
    """
    global _console_configured  # noqa: PLW0603 -- explicit process-wide console policy
    with _initialization_lock:
        if reconfigure or not enabled or not _console_configured:
            _remove_console_handlers()
        _console_configured = True
        if enabled:
            _add_console_handler(level, sys.stdout if stream is None else stream, ColorfulConsoleFormatter())


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
            configured handlers. Defaults to logging.NOTSET, inheriting the task logger's threshold (INFO by default).

    Returns:
        A logger capable of logging messages that will be sent to the configured handlers.
    """
    if name is None:
        name = f"unnamed_logger_{uuid4()}"

    if not root_logger.hasHandlers():
        _configure_runtime_logging()

    logger = logging.getLogger(f"{task_logger.name}.{name}")
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
