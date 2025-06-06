import logging
import os

from _tilebox.grpc.channel import open_channel
from tilebox.datasets.sync.client import Client as DatasetsClient
from tilebox.workflows.cache import JobCache, NoCache
from tilebox.workflows.clusters.client import ClusterClient, ClusterSlugLike, to_cluster_slug
from tilebox.workflows.clusters.service import ClusterService
from tilebox.workflows.data import (
    RunnerContext,
)
from tilebox.workflows.jobs.client import JobClient
from tilebox.workflows.jobs.service import JobService
from tilebox.workflows.observability.tracing import (
    WorkflowTracer,
)
from tilebox.workflows.recurrent_tasks.client import RecurrentTaskClient, RecurrentTaskService
from tilebox.workflows.runner.task_runner import TaskRunner, _LeaseRenewer
from tilebox.workflows.runner.task_service import TaskService


class Client:
    def __init__(self, *, url: str = "https://api.tilebox.com", token: str | None = None) -> None:
        """A client that can be used to access the tilebox workflows service.

        Args:
            url: The URL of the tilebox workflows service, defaults to https://api.tilebox.com
            token: The API key to use for authentication. If not provided, the TILEBOX_API_KEY environment variable
                will be used.
        """
        if token is None:  # if no token is provided, try to get it from the environment
            token = os.environ.get("TILEBOX_API_KEY", None)
        if url == "https://api.tilebox.com" and token is None:
            raise ValueError(
                "No API key provided and no TILEBOX_API_KEY environment variable set. Please specify an API key using "
                "the token argument. For example: `Client(token='YOUR_TILEBOX_API_KEY')`"
            )
        self._auth = {"token": token, "url": url}
        self._channel = open_channel(url, token)

        self._tracer: WorkflowTracer | None = None
        self._logger: logging.Logger | None = None

    def configure_tracing(self, tracer: WorkflowTracer) -> None:
        """
        Configure the tracer to use for tracing of tasks and jobs within the workflow clients.

        The tracer will be used by all task runners and job clients created by this client.

        Calling this method multiple times will replace the existing tracing configuration. However, task runners and
        job clients that have already been created will not be affected by subsequent calls to this method.
        """
        self._tracer = tracer

    def configure_logging(self, logger: logging.Logger) -> None:
        """
        Configure the logger to use for logging of internal events within workflow clients.

        The logger will be used by all task runners created by this client.

        Calling this method multiple times will replace the existing logger. However, task runners
        that have already been created will not be affected by subsequent calls to this method.

        Args:
            logger: The logger to use for logging.
        """
        self._logger = logger

    def jobs(self) -> JobClient:
        """Get a client for the jobs service.

        Returns:
            A client for the jobs service.
        """

        return JobClient(JobService(self._channel), self._tracer)

    def runner(
        self,
        cluster: ClusterSlugLike,
        tasks: list[type] | None = None,
        cache: JobCache | None = None,
        context: type[RunnerContext] | None = None,
    ) -> TaskRunner:
        """Initialize a task runner.

        Args:
            cluster: The cluster to run tasks on.
            tasks: A list of task the runner is able to execute.
            cache: The cache to share between tasks.
            context: The type of the runner context to use. Defaults to RunnerContext.

        Returns:
            A task runner.
        """
        if cache is None:
            cache = NoCache()  # a no-op cache that will raise an error if it's used

        tracer = self._tracer or WorkflowTracer()

        try:
            storage_locations = self.recurrent_tasks().storage_locations()
        except:  # noqa: E722
            # if fetching storage locations fails, we just disable this feature, and don't crash all runners
            # lets refactor this to a lazy loading mechanism in the future
            storage_locations = []

        runner_context_type = context or RunnerContext
        runner_context = runner_context_type(
            tracer._tracer,  # noqa: SLF001
            datasets_client=DatasetsClient(**self._auth),
            storage_locations=storage_locations,
        )

        runner = TaskRunner(
            TaskService(self._channel),
            to_cluster_slug(cluster),
            cache,
            tracer,
            self._logger,
            _LeaseRenewer(**self._auth),
            runner_context,
        )

        if tasks is not None:
            for task in tasks:
                runner.register(task)

        return runner

    def clusters(self) -> ClusterClient:
        """
        Get a client for the clusters service.

        Returns:
            A client for the clusters service.
        """
        return ClusterClient(ClusterService(self._channel))

    def recurrent_tasks(self) -> RecurrentTaskClient:
        """
        Get a client for the recurrent tasks service.

        Returns:
            A client for the recurrent tasks service.
        """
        return RecurrentTaskClient(RecurrentTaskService(self._channel))
