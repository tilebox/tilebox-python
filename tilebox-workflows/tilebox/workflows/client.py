import logging
import os
import warnings
from uuid import UUID, uuid4

from _tilebox.grpc.channel import ConnectStubAdapter, Transport, connect_address, open_channel, parse_channel_info
from tilebox.workflows.automations.client import AutomationClient, AutomationService
from tilebox.workflows.cache import JobCache, NoCache
from tilebox.workflows.clusters.client import ClusterClient, ClusterSlugLike, to_cluster_slug
from tilebox.workflows.clusters.service import ClusterService
from tilebox.workflows.data import (
    RunnerContext,
)
from tilebox.workflows.jobs.client import JobClient
from tilebox.workflows.jobs.service import JobService
from tilebox.workflows.jobs.telemetry_service import TelemetryService
from tilebox.workflows.observability.logging import (
    OTELLoggingHandler,
    StructuredLogger,
    _create_tilebox_logger,
    _create_tilebox_logger_provider,
)
from tilebox.workflows.observability.tracing import WorkflowTracer
from tilebox.workflows.runner.executor import LazyStorageLocations
from tilebox.workflows.runner.task_runner import TaskRunner, _LeaseRenewer
from tilebox.workflows.runner.task_service import TaskService
from tilebox.workflows.task import Task


class Client:
    def __init__(
        self,
        *,
        url: str = "https://api.tilebox.com",
        token: str | None = None,
        name: str | None = None,
        client_id: UUID | None = None,
        transport: Transport = "grpc",
    ) -> None:
        """
        Create a Tilebox workflows client.

        Args:
            url: Tilebox API Url. Defaults to "https://api.tilebox.com".
            token: The API Key to authenticate with. If not set the `TILEBOX_API_KEY` environment variable will be used.
            name: An optional name of the client, used as service.name for telemetry. If not set, defaults to
                the service name provided by `tilebox.workflows.observability.tracing.configure_otel_tracing`,
                or "tilebox-python" if no external tracer is configured.
            client_id: An optional stable id used to scope internal loggers. Defaults to a random id.
            transport: Network transport to use for API requests. Defaults to "grpc". Use "http1" to force
                the Connect protocol over HTTP/1.1 for networks that do not support gRPC over HTTP/2 correctly.
        """
        token = _token_from_env(url, token)
        self._auth: dict[str, str] = {"token": token, "url": url}
        match transport:
            case "grpc":
                self._job_service = open_channel(url, token)
                self._telemetry_service = self._job_service
                self._cluster_service = self._job_service
                self._automation_service = self._job_service
                self._task_service = self._job_service
            case "http1":
                from pyqwest import HTTPVersion, SyncClient, SyncHTTPTransport  # noqa: PLC0415

                from tilebox.workflows.workflows.v1.automation_connect import (  # noqa: PLC0415
                    AutomationServiceClientSync,
                )
                from tilebox.workflows.workflows.v1.job_connect import JobServiceClientSync  # noqa: PLC0415
                from tilebox.workflows.workflows.v1.task_connect import TaskServiceClientSync  # noqa: PLC0415
                from tilebox.workflows.workflows.v1.telemetry_connect import (  # noqa: PLC0415
                    TelemetryQueryServiceClientSync,
                )
                from tilebox.workflows.workflows.v1.workflows_connect import WorkflowsServiceClientSync  # noqa: PLC0415

                address = connect_address(url)
                http_client = SyncClient(SyncHTTPTransport(http_version=HTTPVersion.HTTP1))
                headers = None if token is None else {"authorization": f"Bearer {token}"}
                self._job_service = ConnectStubAdapter(JobServiceClientSync(address, http_client=http_client), headers)
                self._telemetry_service = ConnectStubAdapter(
                    TelemetryQueryServiceClientSync(address, http_client=http_client), headers
                )
                self._cluster_service = ConnectStubAdapter(
                    WorkflowsServiceClientSync(address, http_client=http_client), headers
                )
                self._automation_service = ConnectStubAdapter(
                    AutomationServiceClientSync(address, http_client=http_client), headers
                )
                self._task_service = ConnectStubAdapter(
                    TaskServiceClientSync(address, http_client=http_client), headers
                )
            case _:
                raise ValueError(f"Unsupported transport: {transport}")

        # configure logging and tracing
        self._client_id = client_id or uuid4()  # a random uuid to scope loggers to this client instance
        self._logger_provider = _create_tilebox_logger_provider(service=name, url=url, token=token)

        # task logger is the logger available for users to emit logs from within a Task.execute method, via
        # context.logger
        self._task_logger = _create_tilebox_logger(self._client_id, scope="tasks")
        self._task_logger_handler = OTELLoggingHandler(level=logging.INFO, logger_provider=self._logger_provider)
        self._task_logger.addHandler(self._task_logger_handler)

        # runner logger is the logger used for logging internal events within a task runner, for example when a
        # Tilebox API call fails, or when unexpected errors occur. This logger is not exposed to users,
        # and is only used for logging internal events within the client and task runners.
        self._runner_logger = _create_tilebox_logger(self._client_id, scope="runner")
        self._runner_logger_handler = OTELLoggingHandler(level=logging.INFO, logger_provider=self._logger_provider)
        self._runner_logger.addHandler(self._runner_logger_handler)

        self._tracer = WorkflowTracer(service=name, url=url, token=token)

    def configure_logging(self, level: int | logging.Logger, runner_level: int | None = None) -> None:
        """
        Configure the logger to use for logging of internal events within workflow clients.

        The logger will be used by all task runners created by this client.

        Calling this method multiple times will replace the existing logger. However, task runners
        that have already been created will not be affected by subsequent calls to this method.

        Args:
            logger: The logger to use for logging.
        """
        if not isinstance(level, int):
            warning_message = (
                "Configuring a logger instance directly on a client is deprecated and will be removed in a future "
                "version. If you want to export logs to an external system, configure the tilebox root logger "
                "instance, which you can get with `tilebox.workflows.observability.logging.get_logger()`."
            )
            warnings.warn(
                warning_message,
                DeprecationWarning,
                stacklevel=2,
            )
            # to preserve backwards compatibility with the old API where the first argument was a logger
            self._runner_logger = level
        else:
            # always adjust the level of the handler, not the loggers themselves, to make sure that other logger
            # handlers still receive the logs (for example, if the user configured the tilebox root logger to export
            # all logs at DEBUG level to a file)
            self._task_logger_handler.setLevel(level)
            self._runner_logger_handler.setLevel(runner_level or level)

    def jobs(self) -> JobClient:
        """Get a client for the jobs service.

        Returns:
            A client for the jobs service.
        """

        return JobClient(JobService(self._job_service), TelemetryService(self._telemetry_service), self._tracer)

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
            _LeaseRenewer(**self._auth),
            runner_context,
            task_logger=StructuredLogger(self._task_logger, {}),
            runner_logger=StructuredLogger(self._runner_logger, {}),
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
        return ClusterClient(ClusterService(self._cluster_service))

    def automations(self) -> AutomationClient:
        """
        Get a client for the automations service.

        Returns:
            A client for the automations service.
        """
        return AutomationClient(AutomationService(self._automation_service))


def _token_from_env(url: str, token: str | None) -> str | None:
    if token is None:  # if no token is provided, try to get it from the environment
        token = os.environ.get("TILEBOX_API_KEY", None)

    if token is None and parse_channel_info(url).address == "api.tilebox.com":
        raise ValueError(
            "No API key provided and no TILEBOX_API_KEY environment variable set. Please specify an API key using "
            "the token argument. For example: `Client(token='YOUR_TILEBOX_API_KEY')`"
        )

    return token
