from __future__ import annotations

from typing import TYPE_CHECKING

from tilebox.workflows.cache import JobCache
from tilebox.workflows.data import RunnerContext, TaskIdentifier
from tilebox.workflows.task import Task, TaskMeta

if TYPE_CHECKING:
    from tilebox.workflows.client import Client
    from tilebox.workflows.clusters.client import ClusterSlugLike
    from tilebox.workflows.runner.task_runner import TaskRunner


class Runner:
    def __init__(
        self,
        *,
        tasks: list[type[Task]] | None = None,
        cache: JobCache | None = None,
        context: type[RunnerContext] | None = None,
    ) -> None:
        self.cache = cache
        self.context = context
        self._tasks_by_identifier: dict[TaskIdentifier, type[Task]] = {}

        for task in tasks or []:
            self.register(task)

    def register(self, task: type[Task]) -> None:
        """Register a task that can be executed by this runner."""
        meta = TaskMeta.for_task(task)  # ensures that this is a valid task
        if not meta.executable:
            task_repr = task.__name__
            if meta.identifier.name != task.__name__:
                task_repr += f" ({meta.identifier.name})"
            raise ValueError(
                f"Task {task_repr} is not executable. It must have an execute method in order to "
                f"register it with a task runner."
            )
        if meta.identifier in self._tasks_by_identifier:
            raise ValueError(
                f"Duplicate task identifier: A task '{meta.identifier.name}' with version '{meta.identifier.version}' "
                f"is already registered."
            )
        self._tasks_by_identifier[meta.identifier] = task

    @property
    def task_identifiers(self) -> list[TaskIdentifier]:
        return list(self._tasks_by_identifier)

    @property
    def tasks_by_identifier(self) -> dict[TaskIdentifier, type[Task]]:
        return self._tasks_by_identifier

    def connect_to(self, client: Client, cluster: ClusterSlugLike | None = None) -> TaskRunner:
        """Create a task runner connected to a Tilebox workflows client.

        Args:
            client: The Tilebox workflows client to connect to.
            cluster: The cluster to run tasks on. If not provided, the default cluster will be used.

        Returns:
            A task runner connected to the client's API services.
        """
        return client.runner(
            cluster=cluster,
            tasks=list(self._tasks_by_identifier.values()),
            cache=self.cache,
            context=self.context,
        )
