import logging
import os
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any

from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
    DEFAULT_TRACES_EXPORT_PATH,
    OTLPSpanExporter,
    _append_trace_path,
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import ProxyTracerProvider, get_current_span, get_tracer_provider, set_tracer_provider
from opentelemetry.trace import Span as OTSpan
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

from tilebox.workflows.data import Job
from tilebox.workflows.observability.logging import _LOGGING_NAMESPACE, _get_default_resource, _parse_duration

_AXIOM_ENDPOINT = "https://api.axiom.co/v1/traces"
_AXIOM_TRACES_DATASET_ENV_VAR = "AXIOM_TRACES_DATASET"
_AXIOM_API_KEY_ENV_VAR = "AXIOM_API_KEY"

_PROPAGATOR = TraceContextTextMapPropagator()
_INSTRUMENTATION_MODULE_NAME = "tilebox.com/observability"

_OTEL_TRACES_ENDPOINT_ENV_VAR = "OTEL_TRACES_ENDPOINT"
_OTEL_EXPORT_INTERVAL_ENV_VAR = "OTEL_EXPORT_INTERVAL"


class WorkflowTracer:
    def __init__(self) -> None:
        """Instantiate a tracer from the currently configured global tracer provider."""
        provider = get_tracer_provider()
        if isinstance(provider, ProxyTracerProvider):
            # if no tracer provider is configured, we still don't want to use the no-op tracer, because we
            # want to be able to extract trace_ids and spans, in case other runners / workflow clients have tracing
            # configured. So instead we use a tracer provider without any exporters, which will still create traces
            # and spans, but will not send them anywhere.
            provider = TracerProvider()
        self._tracer = provider.get_tracer(_INSTRUMENTATION_MODULE_NAME)

    # functools.wraps is a bit buggy with class methods, so we are not using it here
    @contextmanager
    def start_as_current_span(self, name: str, *args: Any, **kwargs: Any) -> Iterator[OTSpan]:
        with self._tracer.start_as_current_span(name, *args, **kwargs) as span:
            yield span

    @contextmanager
    def start_job_span(self, job: Job, span_name: str) -> Iterator[OTSpan]:
        context = _PROPAGATOR.extract({"traceparent": job.trace_parent})
        with self._tracer.start_as_current_span(span_name, context=context) as span:
            yield span


def get_trace_parent_of_current_span() -> str:
    carrier: dict[str, str] = {}
    _PROPAGATOR.inject(carrier)
    return carrier["traceparent"]


def _otel_tracer_provider(
    service: str | Resource | None = None,
    endpoint: str | None = None,
    headers: dict[str, str] | None = None,
    export_interval: timedelta | None = None,
) -> TracerProvider:
    resource = _get_default_resource(service)

    provider = TracerProvider(resource=resource)

    if endpoint is None:
        endpoint = os.environ.get(_OTEL_TRACES_ENDPOINT_ENV_VAR, None)
    if endpoint is None:
        raise ValueError(
            f"No OTEL traces endpoint provided and no {_OTEL_TRACES_ENDPOINT_ENV_VAR} environment variable set. Please "
            f"specify an endpoint using the endpoint argument or the environment variable."
        )

    if not endpoint.endswith(DEFAULT_TRACES_EXPORT_PATH):
        endpoint = _append_trace_path(endpoint)

    if export_interval is None:
        export_interval_env = os.environ.get(_OTEL_EXPORT_INTERVAL_ENV_VAR, None)
        if export_interval_env is not None:
            export_interval = _parse_duration(export_interval_env)
    # it's fine if it is none, we will just use the opentelemetry default

    exporter = OTLPSpanExporter(
        endpoint=endpoint,
        headers=headers,
    )
    schedule_delay = int(export_interval.total_seconds() * 1000) if export_interval is not None else None
    batch_processor = BatchSpanProcessor(exporter, schedule_delay_millis=schedule_delay)  # type: ignore[arg-type]

    provider.add_span_processor(batch_processor)

    return provider


class SpanEventLoggingHandler(logging.Handler):
    """A logging handler that adds log messages to active spans as span events."""

    def emit(self, record: logging.LogRecord) -> None:
        span = get_current_span()
        if not span.is_recording():
            return

        # support legacy % formatting usage in messages (even though it's discouraged)
        message = record.msg % record.args if isinstance(record.msg, str) and record.args else record.msg
        created_time = datetime.fromtimestamp(record.created, tz=timezone.utc)

        # add the log message as a span event
        span.add_event(
            "log.message",
            attributes={
                "time": created_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                "message": message,
                "level": record.levelname,
            },
        )


def configure_otel_tracing(
    service: str | Resource | None = None,
    endpoint: str | None = None,
    headers: dict[str, str] | None = None,
    export_interval: timedelta | None = None,
) -> None:
    """
    Configure opentelemetry tracing to a OTLP compatible endpoint.

    This will configure a global opentelemetry tracer provider that can be used to instantiate tracers that will
    send traces and spans to a specified endpoint using the open telemetry protocol for exporting traces and spans.

    Additionally, this will also configure a logging handler that will add log messages to active spans as span events.

    Args:
        service: A string or a resource object to include in all traces. Used to identify the service being traced.
            If a string is provided, it will be used as the service name. If a resource object is provided, it will be
            used as the resource. Defaults to a resource with the service name set to "tilebox.workflows-{process_id}",
            the version set to the version of the package, and the service instance id set to a combination
            of hostname and process id.
        endpoint: The URL of the OTLP compatible endpoint to send traces and spans to. If not provided, the environment
            variable OTEL_TRACES_ENDPOINT will be used. If that is not set either, an error will be raised.
            OTLP compatible endpoints typically have the path name "/v1/traces". If the specified endpoint does not
            include this path, it will be added automatically.
        headers: A dictionary of HTTP headers to include into each request to the endpoint.
        export_interval: The interval at which to export traces and spans to the endpoint. If not provided, the
            environment variable OTEL_EXPORT_INTERVAL will be used. If that is not set either, the default open
            telemetry export interval of 5s will be used.

    Raises:
        ValueError: If no endpoint is provided and no OTEL_TRACES_ENDPOINT environment variable is set.
    """
    provider = _otel_tracer_provider(service, endpoint, headers, export_interval)
    set_tracer_provider(provider)

    # if we configure tracing, we also want to add log messages to active spans, which is a mixture of a logging
    # tracing feature. But configure this here, because we anyways don't need to do this if tracing is not configured.
    root_logger = logging.getLogger(_LOGGING_NAMESPACE)

    has_span_event_handler = False  # in case configure_otel_tracing() is called multiple times, still only one handler
    for handler in root_logger.handlers:
        if isinstance(handler, SpanEventLoggingHandler):
            has_span_event_handler = True
            break

    if not has_span_event_handler:
        root_logger.addHandler(SpanEventLoggingHandler())


def configure_otel_tracing_axiom(
    service: str | Resource | None = None,
    dataset: str | None = None,
    api_key: str | None = None,
) -> None:
    """
    Configure opentelemetry tracing to Axiom.

    This will configure a global opentelemetry tracer provider that can be used to instantiate tracers that will
    send traces and spans to Axiom.

    Args:
        service: A string or a resource object to include in all traces. Used to identify the service being traced.
            If a string is provided, it will be used as the service name. If a resource object is provided, it will be
            used as the resource. Defaults to a resource with the service name set to "tilebox.workflows-{process_id}",
            the version set to the version of the package, and the service instance id set to a combination
            of hostname and process id.
        dataset: The name of the Axiom dataset to ingest traces into. If not provided, the environment variable
            AXIOM_TRACES_DATASET will be used. If that is not set either, an error will be raised.
        api_key: The API key to use for authentication. If not provided, the environment variable AXIOM_API_KEY will be
            used. If that is not set either, an error will be raised.

    Raises:
        ValueError: If no dataset is provided and no AXIOM_TRACES_DATASET environment variable is set
            or no API key is provided and no AXIOM_API_KEY environment variable is set.
    """
    if dataset is None:
        dataset = os.environ.get(_AXIOM_TRACES_DATASET_ENV_VAR, None)
    if api_key is None:
        api_key = os.environ.get(_AXIOM_API_KEY_ENV_VAR, None)

    if dataset is None:
        raise ValueError(
            f"No Axiom traces dataset provided and no {_AXIOM_TRACES_DATASET_ENV_VAR} environment variable set. Please "
            f"specify a dataset using the dataset argument or the environment variable."
        )
    if api_key is None:
        raise ValueError(
            f"No Axiom API Key provided and no {_AXIOM_API_KEY_ENV_VAR} environment variable set. Please "
            f"specify a dataset using the api_key argument or the environment variable."
        )

    configure_otel_tracing(
        service,
        endpoint=_AXIOM_ENDPOINT,
        headers={"Authorization": f"Bearer {api_key}", "X-Axiom-Dataset": dataset},
    )
