from uuid import UUID

from tilebox.workflows.automations.cron import CronTask
from tilebox.workflows.automations.service import AutomationService
from tilebox.workflows.automations.storage_event import StorageEventTask
from tilebox.workflows.clusters.client import ClusterSlugLike, to_cluster_slug
from tilebox.workflows.data import (
    AutomationPrototype,
    CronTrigger,
    StorageEventTrigger,
    StorageLocation,
    TaskSubmission,
)
from tilebox.workflows.task import _task_meta


class AutomationClient:
    def __init__(self, service: AutomationService) -> None:
        self._service = service

    def storage_locations(self) -> list[StorageLocation]:
        """List all available storage locations that can potentially be used as storage event triggers.

        Returns:
            A list of all available storage locations.
        """
        return self._service.list_storage_locations()

    def all(self) -> list[AutomationPrototype]:
        """List all registered automations.

        Returns:
            A list of all registered automations.
        """
        return self._service.list()

    def find(self, automation_id: UUID | str) -> AutomationPrototype:
        """Find an automation by id.

        Args:
            automation_id: The id of the automation to find.

        Returns:
            The automation for the given automation_id.
        """
        if isinstance(automation_id, str):
            automation_id = UUID(automation_id)
        return self._service.get_by_id(automation_id)

    def create_cron_automation(
        self,
        name: str,
        task: CronTask,
        cron_schedules: str | list[str],
        cluster: ClusterSlugLike | None = None,
        max_retries: int = 0,
    ) -> AutomationPrototype:
        """Create a new automation that is triggered by cron schedules.

        Args:
            name: The name of the automation to create.
            task: The task to run.
            cron_schedules: The cron schedules to trigger the task.
            cluster: The cluster to run the task on. If not provided, the default cluster will be used.
            max_retries: The maximum number of retries for the task in case of failure. Defaults to 0.

        Returns:
            The created automation.
        """
        if isinstance(cron_schedules, str):
            cron_schedules = [cron_schedules]

        if not cron_schedules:
            raise ValueError("At least one cron trigger schedule must be provided.")

        automation = AutomationPrototype(
            id=UUID(int=0),
            name=name,
            prototype=TaskSubmission(
                cluster_slug=to_cluster_slug(cluster or ""),
                identifier=_task_meta(task).identifier,
                input=task._serialize_args(),  # noqa: SLF001
                dependencies=[],
                display=task.__class__.__name__,
                max_retries=max_retries,
            ),
            storage_event_triggers=[],
            cron_triggers=[CronTrigger(id=UUID(int=0), schedule=s) for s in cron_schedules],
        )
        return self._service.create(automation)

    def create_storage_event_automation(
        self,
        name: str,
        task: StorageEventTask,
        triggers: list[tuple[StorageLocation, str]] | tuple[StorageLocation, str],
        cluster: ClusterSlugLike | None = None,
        max_retries: int = 0,
    ) -> AutomationPrototype:
        """Create a new automation that is triggered by an object being added to a storage location.

        Args:
            name: The name of the automation to create.
            task: The task to run.
            triggers: Tuples of storage location and glob pattern to trigger the task.
            cluster: The cluster to run the task on. If not provided, the default cluster will be used.
            max_retries: The maximum number of retries for the task in case of failure. Defaults to 0.

        Returns:
            The created automation.
        """
        if not isinstance(triggers, list):
            triggers = [triggers]

        if not triggers:
            raise ValueError("At least one bucket trigger must be provided.")

        automation = AutomationPrototype(
            id=UUID(int=0),
            name=name,
            prototype=TaskSubmission(
                cluster_slug=to_cluster_slug(cluster or ""),
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
        return self._service.create(automation)

    def delete(self, automation_or_id: AutomationPrototype | UUID | str, cancel_jobs: bool = False) -> None:
        """Delete an automation by id.

        Args:
            automation_or_id: The id of the automation to delete or the automation object itself.
            cancel_jobs: Whether to cancel all currently queued or running jobs of the automation. Defaults to False.
        """
        if isinstance(automation_or_id, str):
            automation_id = UUID(automation_or_id)
        elif isinstance(automation_or_id, AutomationPrototype):
            automation_id = automation_or_id.id
        else:
            automation_id = automation_or_id

        self._service.delete(automation_id, cancel_jobs)
