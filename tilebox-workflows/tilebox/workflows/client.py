import logging
import os
import warnings
from collections.abc import Sequence
from typing import Self, TypedDict
from urllib.parse import urlsplit
from uuid import UUID, uuid4

from connectrpc.interceptor import InterceptorSync

from _tilebox.client import Connection, Transport
from tilebox.workflows.automations.client import AutomationClient
from tilebox.workflows.cache import JobCache, NoCache
from tilebox.workflows.clusters.client import ClusterClient, ClusterSlugLike, to_cluster_slug
from tilebox.workflows.data import (
    RunnerContext,
)
from tilebox.workflows.jobs.client import JobClient
from tilebox.workflows.observability._logging import StructuredLogger, internal_logger, task_logger
from tilebox.workflows.observability.logging import (
    initialize_logging,
)
from tilebox.workflows.observability.tracing import WorkflowTracer
from tilebox.workflows.runner.executor import LazyStorageLocations
from tilebox.workflows.runner.task_runner import TaskRunner, _LeaseRenewer
from tilebox.workflows.runner.task_service import TaskService
from tilebox.workflows.storage_locations.client import StorageLocationClient
from tilebox.workflows.task import Task
from tilebox.workflows.v1.automation_connect import AutomationServiceClientSync
from tilebox.workflows.v1.job_connect import JobServiceClientSync
from tilebox.workflows.v1.storage_location_connect import StorageLocationServiceClientSync
from tilebox.workflows.v1.task_connect import TaskServiceClientSync
from tilebox.workflows.v1.telemetry_connect import TelemetryQueryServiceClientSync
from tilebox.workflows.v1.workflows_connect import WorkflowsServiceClientSync
from tilebox.workflows.workflows.client import WorkflowClient


class _ClientAuth(TypedDict):
    url: str
    token: str | None


class Client:
    def __init__(  # noqa: PLR0913
        self,
        *,
        url: str | None = None,
        token: str | None = None,
        name: str | None = None,
        client_id: UUID | None = None,
        transport: Transport = "http2",
        interceptors: Sequence[InterceptorSync] = (),
    ) -> None:
        """
        Create a Tilebox workflows client.

        Args:
            url: Tilebox API URL. If not set, uses the `TILEBOX_API_URL` environment variable,
                or defaulting to "https://api.tilebox.com".
            token: The API Key to authenticate with. If not set the `TILEBOX_API_KEY` environment variable will be used.
            name: An optional name of the client, used as service.name for telemetry. If not set, defaults to
                the service name provided by `tilebox.workflows.observability.tracing.configure_otel_tracing`,
                or "tilebox-python" if no external tracer is configured.
            client_id: An optional client identifier. Logging is shared across the process.
            transport: Connect HTTP version: "http2" (default), or "http1" for proxies that block HTTP/2.
                The legacy "grpc" spelling is an alias for "http2".
            interceptors: Connect interceptors applied to API requests.
        """
        if url is None:
            url = os.environ.get("TILEBOX_API_URL") or "https://api.tilebox.com"
        token = _token_from_env(url, token)
        self._auth: _ClientAuth = {"token": token, "url": url}
        self._connection = Connection(url, token, transport=transport, interceptors=interceptors)
        self._job_service = self._connection.client(JobServiceClientSync)
        self._telemetry_service = self._connection.client(TelemetryQueryServiceClientSync)
        self._cluster_service = self._connection.client(WorkflowsServiceClientSync)
        self._workflow_service = self._cluster_service
        self._automation_service = self._connection.client(AutomationServiceClientSync)
        self._storage_location_service = self._connection.client(StorageLocationServiceClientSync)
        self._task_service = self._connection.client(TaskServiceClientSync)

        self._client_id = client_id or uuid4()
        self._name = name
        self._task_logger = StructuredLogger(task_logger)
        self._runner_logger = StructuredLogger(internal_logger)
        self._tracer = WorkflowTracer(service=name, url=url, token=token)

    def close(self) -> None:
        """Close the API connection and flush this client's tracing exporter."""
        try:
            self._tracer.close()
        finally:
            self._connection.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def configure_logging(self, level: int | logging.Logger, runner_level: int | None = None) -> None:  # noqa: ARG002
        """Deprecated compatibility no-op. Runner logging is initialized automatically."""
        warnings.warn(
            "Client.configure_logging() is deprecated and no longer needed; logging is initialized automatically. "
            "This call has no effect. Use tilebox.workflows.observability.logging.configure_log_level() "
            "or TILEBOX_LOG_LEVEL / TILEBOX_DEBUG to change process-wide thresholds.",
            DeprecationWarning,
            stacklevel=2,
        )

    def jobs(self) -> JobClient:
        """Get a client for the jobs service.

        Returns:
            A client for the jobs service.
        """

        return JobClient(self._job_service, self._telemetry_service, self._tracer)

    def runner(
        self,
        cluster: ClusterSlugLike | None = None,
        tasks: list[type[Task]] | None = None,
        cache: JobCache | None = None,
        context: type[RunnerContext] | None = None,
    ) -> TaskRunner:
        """Initialize a task runner.

        Args:
            cluster: The cluster to run tasks on. If not provided, the default cluster will be used.
            tasks: A list of task the runner is able to execute.
            cache: The cache to share between tasks.
            context: The type of the runner context to use. Defaults to RunnerContext.

        Returns:
            A task runner.
        """
        # Stage 3: direct runners have no initialization RPC. Configure API + stdout
        # logging here, before API calls or the lease-renewal process are started.
        initialize_logging(**self._auth, service=self._name)
        if cache is None:
            cache = NoCache()  # a no-op cache that will raise an error if it's used

        found_cluster = self.clusters().find(to_cluster_slug(cluster or ""))

        runner_context_type = context or RunnerContext
        runner_context = runner_context_type(self._tracer)
        runner_context.storage_locations = LazyStorageLocations(self, runner_context)

        task_runner = TaskRunner(
            TaskService(self._task_service),
            found_cluster.slug,
            cache,
            self._tracer,
            _LeaseRenewer(**self._auth, transport=self._connection.transport),
            runner_context,
            task_logger=self._task_logger,
            runner_logger=self._runner_logger,
        )

        for task in tasks or []:
            task_runner.register(task)

        return task_runner

    def clusters(self) -> ClusterClient:
        """
        Get a client for the clusters service.

        Returns:
            A client for the clusters service.
        """
        return ClusterClient(self._cluster_service)

    def workflows(self) -> WorkflowClient:
        """
        Get a client for the workflows service.

        Returns:
            A client for the workflows service.
        """
        return WorkflowClient(self._workflow_service)

    def automations(self) -> AutomationClient:
        """
        Get a client for the automations service.

        Returns:
            A client for the automations service.
        """
        return AutomationClient(self._automation_service)

    def storage_locations(self) -> StorageLocationClient:
        """Get a client for storage locations."""
        return StorageLocationClient(self._storage_location_service)


def _token_from_env(url: str, token: str | None) -> str | None:
    if token is None:  # if no token is provided, try to get it from the environment
        token = os.environ.get("TILEBOX_API_KEY", None)

    if token is None and urlsplit(url if "://" in url else f"https://{url}").hostname == "api.tilebox.com":
        raise ValueError(
            "No API key provided and no TILEBOX_API_KEY environment variable set. Please specify an API key using "
            "the token argument. For example: `Client(token='YOUR_TILEBOX_API_KEY')`"
        )

    return token
