from __future__ import annotations

import os
from datetime import timedelta

from opentelemetry import metrics
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.metrics._internal.instrument import Gauge
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader

from tilebox.workflows.observability.execution_attributes import current_execution_attributes_dict
from tilebox.workflows.observability.logging import _get_default_resource, _parse_duration

_AXIOM_ENDPOINT = "https://api.axiom.co/v1/metrics"
_AXIOM_METRICS_DATASET_ENV_VAR = "AXIOM_METRICS_DATASET"
_AXIOM_API_KEY_ENV_VAR = "AXIOM_API_KEY"

_OTEL_METRICS_ENDPOINT_ENV_VAR = "OTEL_METRICS_ENDPOINT"
_OTEL_EXPORT_INTERVAL_ENV_VAR = "OTEL_EXPORT_INTERVAL"

_DEFAULT_METRICS_EXPORT_PATH = "/v1/metrics"


def _append_metrics_path(endpoint: str) -> str:
    if endpoint.endswith("/"):
        return endpoint + _DEFAULT_METRICS_EXPORT_PATH.lstrip("/")
    return endpoint + _DEFAULT_METRICS_EXPORT_PATH


def _otel_metric_reader(
    endpoint: str | None = None,
    headers: dict[str, str] | None = None,
    export_interval: timedelta | None = None,
) -> PeriodicExportingMetricReader:
    if endpoint is None:
        endpoint = os.environ.get(_OTEL_METRICS_ENDPOINT_ENV_VAR, None)
    if endpoint is None:
        raise ValueError(
            f"No OTEL metrics endpoint provided and no {_OTEL_METRICS_ENDPOINT_ENV_VAR} environment variable set. "
            f"Please specify an endpoint using the endpoint argument or the environment variable."
        )

    if not endpoint.endswith(_DEFAULT_METRICS_EXPORT_PATH):
        endpoint = _append_metrics_path(endpoint)

    if export_interval is None:
        export_interval_env = os.environ.get(_OTEL_EXPORT_INTERVAL_ENV_VAR, None)
        if export_interval_env is not None:
            export_interval = _parse_duration(export_interval_env)

    exporter = OTLPMetricExporter(
        endpoint=endpoint,
        headers=headers,
    )
    export_interval_millis = int(export_interval.total_seconds() * 1000) if export_interval is not None else None
    return PeriodicExportingMetricReader(exporter, export_interval_millis=export_interval_millis)


def configure_otel_metrics(
    service: str | None = None,
    endpoint: str | None = None,
    headers: dict[str, str] | None = None,
    export_interval: timedelta | None = None,
) -> None:
    """
    Configure opentelemetry metrics to an OTLP compatible endpoint.

    This will configure a global opentelemetry meter provider that exports metrics to the specified endpoint.
    Meters and instruments created via `opentelemetry.metrics.get_meter()` will automatically use this provider.

    Args:
        service: A string used to identify the service in metric resource attributes.
            Defaults to "tilebox.workflows-{process_id}".
        endpoint: The URL of the OTLP compatible endpoint to send metrics to. If not provided, the environment
            variable OTEL_METRICS_ENDPOINT will be used. If that is not set either, an error will be raised.
            OTLP compatible endpoints typically have the path name "/v1/metrics". If the specified endpoint does not
            include this path, it will be added automatically.
        headers: A dictionary of HTTP headers to include into each request to the endpoint.
        export_interval: The interval at which to export metrics to the endpoint. If not provided, the
            environment variable OTEL_EXPORT_INTERVAL will be used. If that is not set either, the default open
            telemetry export interval will be used.

    Raises:
        ValueError: If no endpoint is provided and no OTEL_METRICS_ENDPOINT environment variable is set.
    """
    resource = _get_default_resource(service)
    reader = _otel_metric_reader(endpoint, headers, export_interval)
    provider = MeterProvider(resource=resource, metric_readers=[reader])
    metrics.set_meter_provider(provider)


def configure_otel_metrics_axiom(
    service: str | None = None,
    dataset: str | None = None,
    api_key: str | None = None,
) -> None:
    """
    Configure opentelemetry metrics to Axiom.

    This will configure a global opentelemetry meter provider that exports metrics to Axiom.

    Args:
        service: A string used to identify the service in metric resource attributes.
            Defaults to "tilebox.workflows-{process_id}".
        dataset: The name of the Axiom dataset to ingest metrics into. If not provided, the environment variable
            AXIOM_METRICS_DATASET will be used. If that is not set either, an error will be raised.
        api_key: The API key to use for authentication. If not provided, the environment variable AXIOM_API_KEY will be
            used. If that is not set either, an error will be raised.

    Raises:
        ValueError: If no dataset is provided and no AXIOM_METRICS_DATASET environment variable is set
            or no API key is provided and no AXIOM_API_KEY environment variable is set.
    """
    if dataset is None:
        dataset = os.environ.get(_AXIOM_METRICS_DATASET_ENV_VAR, None)
    if api_key is None:
        api_key = os.environ.get(_AXIOM_API_KEY_ENV_VAR, None)

    if dataset is None:
        raise ValueError(
            f"No Axiom metrics dataset provided and no {_AXIOM_METRICS_DATASET_ENV_VAR} environment variable set. "
            f"Please specify a dataset using the dataset argument or the environment variable."
        )
    if api_key is None:
        raise ValueError(
            f"No Axiom API Key provided and no {_AXIOM_API_KEY_ENV_VAR} environment variable set. "
            f"Please specify an API key using the api_key argument or the environment variable."
        )

    configure_otel_metrics(
        service,
        endpoint=_AXIOM_ENDPOINT,
        headers={"Authorization": f"Bearer {api_key}", "X-Axiom-Dataset": dataset},
    )


class _Counter:
    """A counter wrapper that automatically injects execution attributes (job_id, task_id)."""

    def __init__(self, counter: metrics.Counter) -> None:
        self._counter = counter

    def add(self, amount: int | float, attributes: dict[str, str] | None = None) -> None:
        merged = current_execution_attributes_dict()
        if attributes:
            merged.update(attributes)
        self._counter.add(amount, merged)


class _Histogram:
    """A histogram wrapper that automatically injects execution attributes (job_id, task_id)."""

    def __init__(self, histogram: metrics.Histogram) -> None:
        self._histogram = histogram

    def record(self, amount: int | float, attributes: dict[str, str] | None = None) -> None:
        merged = current_execution_attributes_dict()
        if attributes:
            merged.update(attributes)
        self._histogram.record(amount, merged)


class _UpDownCounter:
    """An up-down counter wrapper that automatically injects execution attributes (job_id, task_id)."""

    def __init__(self, counter: metrics.UpDownCounter) -> None:
        self._counter = counter

    def add(self, amount: int | float, attributes: dict[str, str] | None = None) -> None:
        merged = current_execution_attributes_dict()
        if attributes:
            merged.update(attributes)
        self._counter.add(amount, merged)


class _Gauge:
    """A gauge wrapper that automatically injects execution attributes (job_id, task_id)."""

    def __init__(self, gauge: Gauge) -> None:
        self._gauge = gauge

    def set(self, amount: int | float, attributes: dict[str, str] | None = None) -> None:
        merged = current_execution_attributes_dict()
        if attributes:
            merged.update(attributes)
        self._gauge.set(amount, merged)


class Meter:
    """
    A meter wrapper that creates instruments which automatically include execution attributes
    (job_id, task_id) when recording measurements within a task execution context.
    """

    def __init__(self, name: str) -> None:
        self._meter = metrics.get_meter(name)

    def create_counter(self, name: str, unit: str = "", description: str = "") -> _Counter:
        return _Counter(self._meter.create_counter(name, unit=unit, description=description))

    def create_histogram(self, name: str, unit: str = "", description: str = "") -> _Histogram:
        return _Histogram(self._meter.create_histogram(name, unit=unit, description=description))

    def create_up_down_counter(self, name: str, unit: str = "", description: str = "") -> _UpDownCounter:
        return _UpDownCounter(self._meter.create_up_down_counter(name, unit=unit, description=description))

    def create_gauge(self, name: str, unit: str = "", description: str = "") -> _Gauge:
        return _Gauge(self._meter.create_gauge(name, unit=unit, description=description))


def get_meter(name: str) -> Meter:
    """
    Get a meter with the given name from the globally configured meter provider.

    Use this meter to create instruments (counters, histograms, gauges, etc.) that will
    automatically include execution attributes (job_id, task_id) when recording measurements
    within a task execution context.

    Args:
        name: A name for the meter, typically the module or component name.

    Returns:
        A Meter instance whose instruments automatically attach execution attributes.
    """
    return Meter(name)
