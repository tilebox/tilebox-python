import asyncio
from unittest.mock import MagicMock
from uuid import UUID, uuid4

from google.protobuf.empty_pb2 import Empty
from hypothesis.stateful import Bundle, RuleBasedStateMachine, consumes, rule
from hypothesis.strategies import lists
from tests.tasks_data import alphanumerical_text, cron_triggers, storage_event_triggers, task_identifiers

from _tilebox.grpc.error import NotFoundError
from tilebox.workflows.clients.recurrent_tasks import RecurrentTaskClient, RecurrentTaskService
from tilebox.workflows.data import (
    CronTrigger,
    RecurrentTaskPrototype,
    StorageEventTrigger,
    TaskIdentifier,
    uuid_message_to_uuid,
    uuid_to_uuid_message,
)
from tilebox.workflows.recurrent_tasks import CronTask, StorageEventTask
from tilebox.workflows.workflowsv1.core_pb2 import UUID as UUIDMessage  # noqa: N811
from tilebox.workflows.workflowsv1.recurrent_task_pb2 import CronTrigger as CronTriggerMessage
from tilebox.workflows.workflowsv1.recurrent_task_pb2 import RecurrentTaskPrototype as RecurrentTaskPrototypeMessage
from tilebox.workflows.workflowsv1.recurrent_task_pb2 import RecurrentTasks
from tilebox.workflows.workflowsv1.recurrent_task_pb2 import StorageEventTrigger as StorageEventTriggerMessage
from tilebox.workflows.workflowsv1.recurrent_task_pb2_grpc import RecurrentTaskServiceStub


class MockRecurrentTaskService(RecurrentTaskServiceStub):
    """A mock implementation of the gRPC recurrent task service, that stores recurrent tasks in memory as a dict."""

    def __init__(self) -> None:
        self.recurrent_tasks: dict[UUID, RecurrentTaskPrototypeMessage] = {}

    async def CreateRecurrentTask(self, req: RecurrentTaskPrototypeMessage) -> RecurrentTaskPrototypeMessage:  # noqa: N802
        task_id = uuid4()
        created = RecurrentTaskPrototypeMessage(
            id=uuid_to_uuid_message(task_id),  # assign an auto generated id to the task
            name=req.name,
            prototype=req.prototype,
            # assign auto generated ids to the triggers
            storage_event_triggers=[
                StorageEventTriggerMessage(
                    id=uuid_to_uuid_message(uuid4()), storage_location=st.storage_location, glob_pattern=st.glob_pattern
                )
                for st in req.storage_event_triggers
            ],
            cron_triggers=[
                CronTriggerMessage(id=uuid_to_uuid_message(uuid4()), schedule=ct.schedule) for ct in req.cron_triggers
            ],
        )

        self.recurrent_tasks[task_id] = created
        return created

    async def UpdateRecurrentTask(self, req: RecurrentTaskPrototypeMessage) -> RecurrentTaskPrototypeMessage:  # noqa: N802
        task_id = uuid_message_to_uuid(req.id)
        if task_id not in self.recurrent_tasks:
            raise NotFoundError(f"Recurrent Task {task_id} not found")
        self.recurrent_tasks[task_id] = req
        return req

    async def GetRecurrentTask(self, req: UUIDMessage) -> RecurrentTaskPrototypeMessage:  # noqa: N802
        task_id = uuid_message_to_uuid(req)
        if task_id in self.recurrent_tasks:
            return self.recurrent_tasks[task_id]
        raise NotFoundError(f"Recurrent Task {task_id} not found")

    async def DeleteRecurrentTask(self, req: UUIDMessage) -> None:  # noqa: N802
        task_id = uuid_message_to_uuid(req)
        if task_id in self.recurrent_tasks:
            del self.recurrent_tasks[task_id]
        else:
            raise NotFoundError(f"Recurrent Task {task_id} not found")

    async def ListRecurrentTasks(self, req: Empty) -> RecurrentTasks:  # noqa: N802
        _ = req
        return RecurrentTasks(tasks=list(self.recurrent_tasks.values()))


class RecurrentTaskCRUDOperations(RuleBasedStateMachine):
    """
    A state machine that tests the CRUD operations of the Recurrent Tasks client.

    The rules defined here will be executed in random order by Hypothesis, and each rule can be called any number of
    times. The state of the state machine is defined by the bundles, which are collections of objects that can be
    inserted into the state machine by the rules. Rules can also consume objects from the bundles, which will remove
    them from the state machine state.

    For more information see:
    https://hypothesis.readthedocs.io/en/latest/stateful.html
    """

    def __init__(self) -> None:
        super().__init__()
        service = RecurrentTaskService(MagicMock())
        service.service = MockRecurrentTaskService()  # mock the gRPC service
        self.client = RecurrentTaskClient(service)
        self.count_recurrent_tasks = 0

    inserted_recurrent_tasks: Bundle[RecurrentTaskPrototype] = Bundle("recurrent_tasks")

    @rule(
        target=inserted_recurrent_tasks,
        task_name=alphanumerical_text(min_size=4, max_size=50),
        cluster_slug=alphanumerical_text(min_size=4, max_size=20),
        task_identifier=task_identifiers(),
        cron_triggers=lists(cron_triggers(), min_size=1, max_size=10),
    )
    def create_recurring_cron_task(
        self,
        task_name: str,
        cluster_slug: str,
        task_identifier: TaskIdentifier,
        cron_triggers: list[CronTrigger],
    ) -> RecurrentTaskPrototype:
        self.count_recurrent_tasks += 1
        triggers = [t.schedule for t in cron_triggers]

        class TestCronTask(CronTask):
            some_arg: str

            @staticmethod
            def identifier() -> tuple[str, str]:
                return task_identifier.name, task_identifier.version

        task = TestCronTask(task_name)  # task_name reused to serialize the task input

        # RuleBasedStateMachine does not support async functions, so we use asyncio.run instead of await
        return asyncio.run(self.client.create_recurring_cron_task(task_name, cluster_slug, task, triggers))

    @rule(
        target=inserted_recurrent_tasks,
        task_name=alphanumerical_text(min_size=4, max_size=50),
        cluster_slug=alphanumerical_text(min_size=4, max_size=20),
        task_identifier=task_identifiers(),
        storage_event_triggers=lists(storage_event_triggers(), min_size=1, max_size=10),
    )
    def create_recurring_storage_event_task(
        self,
        task_name: str,
        cluster_slug: str,
        task_identifier: TaskIdentifier,
        storage_event_triggers: list[StorageEventTrigger],
    ) -> RecurrentTaskPrototype:
        self.count_recurrent_tasks += 1
        triggers = [(t.storage_location, t.glob_pattern) for t in storage_event_triggers]

        class TestStorageEventTask(StorageEventTask):
            some_arg: str

            @staticmethod
            def identifier() -> tuple[str, str]:
                return task_identifier.name, task_identifier.version

        task = TestStorageEventTask(task_name)  # task_name reused to serialize the task input

        # RuleBasedStateMachine does not support async functions, so we use asyncio.run instead of await
        return asyncio.run(self.client.create_recurring_storage_event_task(task_name, cluster_slug, task, triggers))

    @rule(recurrent_task=inserted_recurrent_tasks)
    def get_recurrent_task(self, recurrent_task: RecurrentTaskPrototype) -> None:
        got = asyncio.run(self.client.find(recurrent_task.id))
        assert recurrent_task.id == got.id
        assert recurrent_task.name == got.name

    @rule(recurrent_task=consumes(inserted_recurrent_tasks))  # consumes -> remove from bundle afterwards
    def delete_recurrent_task(self, recurrent_task: RecurrentTaskPrototype) -> None:
        self.count_recurrent_tasks -= 1
        asyncio.run(self.client.delete(recurrent_task))

    @rule()
    def list_recurrent_tasks(self) -> None:
        recurrent_tasks = asyncio.run(self.client.all())
        assert len(recurrent_tasks) == self.count_recurrent_tasks


# make pytest pick up the test cases from the state machine
TestRecurrentTaskCRUDOperations = RecurrentTaskCRUDOperations.TestCase
