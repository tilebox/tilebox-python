from uuid import UUID

from tilebox.workflows.clusters.client import ClusterSlugLike, to_cluster_slug
from tilebox.workflows.data import (
    CronTrigger,
    RecurrentTaskPrototype,
    StorageEventTrigger,
    StorageLocation,
    TaskSubmission,
)
from tilebox.workflows.recurrent_tasks.cron import CronTask
from tilebox.workflows.recurrent_tasks.service import RecurrentTaskService
from tilebox.workflows.recurrent_tasks.storage_event import StorageEventTask
from tilebox.workflows.task import _task_meta


class RecurrentTaskClient:
    def __init__(self, service: RecurrentTaskService) -> None:
        self._service = service

    def storage_locations(self) -> list[StorageLocation]:
        """List all available storage locations that can potentially be used as storage event triggers.

        Returns:
            A list of all available storage locations.
        """
        return self._service.list_storage_locations()

    def all(self) -> list[RecurrentTaskPrototype]:
        """List all registered recurrent tasks.

        Returns:
            A list of all registered recurrent tasks.
        """
        return self._service.list()

    def find(self, task_id: UUID | str) -> RecurrentTaskPrototype:
        """Find a recurrent task by id.

        Args:
            task_id: The id of the recurrent task to find.

        Returns:
            The recurrent task for the given task_id.
        """
        if isinstance(task_id, str):
            task_id = UUID(task_id)
        return self._service.get_by_id(task_id)

    def create_recurring_cron_task(
        self,
        name: str,
        task: CronTask,
        cron_schedules: str | list[str],
        cluster: ClusterSlugLike,
        max_retries: int = 0,
    ) -> RecurrentTaskPrototype:
        """Create a new recurrent task that is triggered by cron schedules.

        Args:
            name: The name of the recurrent task to create.
            task: The task to run.
            cron_schedules: The cron schedules to trigger the task.
            cluster: The cluster to run the task on.
            max_retries: The maximum number of retries for the task in case of failure. Defaults to 0.

        Returns:
            The created recurrent task.
        """
        if isinstance(cron_schedules, str):
            cron_schedules = [cron_schedules]

        if not cron_schedules:
            raise ValueError("At least one cron trigger schedule must be provided.")

        recurrent_task = RecurrentTaskPrototype(
            id=UUID(int=0),
            name=name,
            prototype=TaskSubmission(
                cluster_slug=to_cluster_slug(cluster),
                identifier=_task_meta(task).identifier,
                input=task._serialize_args(),  # noqa: SLF001
                dependencies=[],
                display=task.__class__.__name__,
                max_retries=max_retries,
            ),
            storage_event_triggers=[],
            cron_triggers=[CronTrigger(id=UUID(int=0), schedule=s) for s in cron_schedules],
        )
        return self._service.create(recurrent_task)

    def create_recurring_storage_event_task(
        self,
        name: str,
        task: StorageEventTask,
        triggers: list[tuple[StorageLocation, str]] | tuple[StorageLocation, str],
        cluster: ClusterSlugLike,
        max_retries: int = 0,
    ) -> RecurrentTaskPrototype:
        """Create a new recurrent task that is triggered by an object being added to a storage location.

        Args:
            name: The name of the recurrent task to create.
            task: The task to run.
            triggers: Tuples of storage location and glob pattern to trigger the task.
            cluster: The cluster to run the task on.
            max_retries: The maximum number of retries for the task in case of failure. Defaults to 0.

        Returns:
            The created recurrent task.
        """
        if not isinstance(triggers, list):
            triggers = [triggers]

        if not triggers:
            raise ValueError("At least one bucket trigger must be provided.")

        recurrent_task = RecurrentTaskPrototype(
            id=UUID(int=0),
            name=name,
            prototype=TaskSubmission(
                cluster_slug=to_cluster_slug(cluster),
                identifier=_task_meta(task).identifier,
                input=task._serialize_args(),  # noqa: SLF001
                dependencies=[],
                display=task.__class__.__name__,
                max_retries=max_retries,
            ),
            storage_event_triggers=[
                StorageEventTrigger(id=UUID(int=0), storage_location=sl, glob_pattern=g) for sl, g in triggers
            ],
            cron_triggers=[],
        )
        return self._service.create(recurrent_task)

    def delete(self, task_or_id: RecurrentTaskPrototype | UUID | str) -> None:
        """Delete a recurrent task by id.

        Args:
            task_id: The id of the recurrent task to delete.
        """
        if isinstance(task_or_id, str):
            task_id = UUID(task_or_id)
        elif isinstance(task_or_id, RecurrentTaskPrototype):
            task_id = task_or_id.id
        else:
            task_id = task_or_id

        self._service.delete(task_id)
