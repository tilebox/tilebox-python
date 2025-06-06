from uuid import UUID

from google.protobuf.empty_pb2 import Empty
from grpc.aio import Channel

from _tilebox.grpc.aio.syncify import Syncifiable
from tilebox.workflows.data import (
    CronTrigger,
    RecurrentTaskPrototype,
    StorageEventTrigger,
    StorageLocation,
    TaskSubmission,
    uuid_to_uuid_message,
)
from tilebox.workflows.recurrent_tasks.cron import AsyncCronTask, SyncCronTask
from tilebox.workflows.recurrent_tasks.storage_event import AsyncStorageEventTask, SyncStorageEventTask
from tilebox.workflows.task import _task_meta
from tilebox.workflows.workflowsv1.recurrent_task_pb2 import RecurrentTaskPrototype as RecurrentTaskPrototypeMessage
from tilebox.workflows.workflowsv1.recurrent_task_pb2 import RecurrentTasks, StorageLocations
from tilebox.workflows.workflowsv1.recurrent_task_pb2_grpc import RecurrentTaskServiceStub


class RecurrentTaskService:
    def __init__(self, channel: Channel) -> None:
        """
        A wrapper around the RecurrentTasksServiceStub that provides a more pythonic interface and converts the protobuf
        messages to and from the data classes used in the rest of the tilebox-workflows codebase.

        Args:
            channel: The gRPC channel to use for the service.
        """
        self.service = RecurrentTaskServiceStub(channel)

    async def list_storage_locations(self) -> list[StorageLocation]:
        """List all storage locations.

        Returns:
            A list of storage locations.
        """
        response: StorageLocations = await self.service.ListStorageLocations(Empty())
        return [StorageLocation.from_message(sl) for sl in response.locations]

    async def list(self) -> list[RecurrentTaskPrototype]:
        """List all recurrent tasks.

        Returns:
            A list of recurrent tasks.
        """
        response: RecurrentTasks = await self.service.ListRecurrentTasks(Empty())
        return [RecurrentTaskPrototype.from_message(task) for task in response.tasks]

    async def get_by_id(self, task_id: UUID) -> RecurrentTaskPrototype:
        """Get a recurrent task by its id.

        Args:
            task_id: The UUID of the task to get.

        Returns:
            The recurrent task.
        """
        response: RecurrentTaskPrototypeMessage = await self.service.GetRecurrentTask(uuid_to_uuid_message(task_id))
        return RecurrentTaskPrototype.from_message(response)

    async def create(self, task: RecurrentTaskPrototype) -> RecurrentTaskPrototype:
        """Create a new recurrent task.

        Args:
            task: The recurrent task to create.

        Returns:
            The created recurrent task.
        """
        response: RecurrentTaskPrototypeMessage = await self.service.CreateRecurrentTask(task.to_message())
        return RecurrentTaskPrototype.from_message(response)

    async def update(self, task: RecurrentTaskPrototype) -> RecurrentTaskPrototype:
        """Update a recurrent task.

        Args:
            task: The recurrent task to update.

        Returns:
            The updated recurrent task.
        """
        response: RecurrentTaskPrototypeMessage = await self.service.UpdateRecurrentTask(task.to_message())
        return RecurrentTaskPrototype.from_message(response)

    async def delete(self, task_id: UUID) -> None:
        """Delete a recurrent task.

        Args:
            task_id: The UUID of the task to delete.
        """
        await self.service.DeleteRecurrentTask(uuid_to_uuid_message(task_id))


class RecurrentTaskClient(Syncifiable):
    def __init__(self, service: RecurrentTaskService) -> None:
        self._service = service

    async def storage_locations(self) -> list[StorageLocation]:
        """List all available storage locations that can potentially be used as storage event triggers.

        Returns:
            A list of all available storage locations.
        """
        return await self._service.list_storage_locations()

    async def all(self) -> list[RecurrentTaskPrototype]:
        """List all registered recurrent tasks.

        Returns:
            A list of all registered recurrent tasks.
        """
        return await self._service.list()

    async def find(self, task_id: UUID | str) -> RecurrentTaskPrototype:
        """Find a recurrent task by id.

        Args:
            task_id: The id of the recurrent task to find.

        Returns:
            The recurrent task for the given task_id.
        """
        if isinstance(task_id, str):
            task_id = UUID(task_id)
        return await self._service.get_by_id(task_id)

    async def create_recurring_cron_task(
        self,
        name: str,
        cluster_slug: str,
        task: SyncCronTask | AsyncCronTask,
        cron_triggers: str | list[str],
        max_retries: int = 0,
    ) -> RecurrentTaskPrototype:
        """Create a new recurrent task that is triggered by cron schedules.

        Args:
            name: The name of the recurrent task to create.
            cluster_slug: The slug of the cluster to run the task on.
            task: The task to run.
            cron_schedules: The cron schedules to trigger the task.

        Returns:
            The created recurrent task.
        """
        if isinstance(cron_triggers, str):
            cron_triggers = [cron_triggers]

        if not cron_triggers:
            raise ValueError("At least one cron trigger must be provided.")

        recurrent_task = RecurrentTaskPrototype(
            id=UUID(int=0),
            name=name,
            prototype=TaskSubmission(
                cluster_slug=cluster_slug,
                identifier=_task_meta(task).identifier,
                input=task._serialize_args(),  # noqa: SLF001
                dependencies=[],
                display=task.__class__.__name__,
                max_retries=max_retries,
            ),
            storage_event_triggers=[],
            cron_triggers=[CronTrigger(id=UUID(int=0), schedule=s) for s in cron_triggers],
        )
        return await self._service.create(recurrent_task)

    async def create_recurring_storage_event_task(
        self,
        name: str,
        cluster_slug: str,
        task: SyncStorageEventTask | AsyncStorageEventTask,
        triggers: list[tuple[StorageLocation, str]] | tuple[StorageLocation, str],
        max_retries: int = 0,
    ) -> RecurrentTaskPrototype:
        """Create a new recurrent task that is triggered by an object being added to a storage location.

        Args:
            name: The name of the recurrent task to create.
            cluster_slug: The slug of the cluster to run the task on.
            task: The task to run.
            triggers: Tuples of storage location and glob pattern to trigger the task.

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
                cluster_slug=cluster_slug,
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
        return await self._service.create(recurrent_task)

    async def delete(self, task_or_id: RecurrentTaskPrototype | UUID | str) -> None:
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
        await self._service.delete(task_id)
