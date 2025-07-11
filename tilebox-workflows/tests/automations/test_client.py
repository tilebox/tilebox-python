from unittest.mock import MagicMock
from uuid import UUID, uuid4

from google.protobuf.empty_pb2 import Empty
from hypothesis.stateful import Bundle, RuleBasedStateMachine, consumes, rule
from hypothesis.strategies import lists
from tests.tasks_data import alphanumerical_text, cron_triggers, storage_event_triggers, task_identifiers

from _tilebox.grpc.error import NotFoundError
from tilebox.workflows.automations import CronTask, StorageEventTask
from tilebox.workflows.automations.client import AutomationClient, AutomationService
from tilebox.workflows.data import (
    AutomationPrototype,
    CronTrigger,
    StorageEventTrigger,
    TaskIdentifier,
    uuid_message_to_uuid,
    uuid_to_uuid_message,
)
from tilebox.workflows.workflows.v1.automation_pb2 import AutomationPrototype as AutomationPrototypeMessage
from tilebox.workflows.workflows.v1.automation_pb2 import Automations, DeleteAutomationRequest
from tilebox.workflows.workflows.v1.automation_pb2 import CronTrigger as CronTriggerMessage
from tilebox.workflows.workflows.v1.automation_pb2 import StorageEventTrigger as StorageEventTriggerMessage
from tilebox.workflows.workflows.v1.automation_pb2_grpc import AutomationServiceStub
from tilebox.workflows.workflows.v1.core_pb2 import UUID as UUIDMessage  # noqa: N811


class MockAutomationService(AutomationServiceStub):
    """A mock implementation of the gRPC automation service, that stores automations in memory as a dict."""

    def __init__(self) -> None:
        self.automations: dict[UUID, AutomationPrototypeMessage] = {}

    def CreateAutomation(self, req: AutomationPrototypeMessage) -> AutomationPrototypeMessage:  # noqa: N802
        automation_id = uuid4()
        created = AutomationPrototypeMessage(
            id=uuid_to_uuid_message(automation_id),  # assign an auto generated id to the automation
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

        self.automations[automation_id] = created
        return created

    def UpdateAutomation(self, req: AutomationPrototypeMessage) -> AutomationPrototypeMessage:  # noqa: N802
        automation_id = uuid_message_to_uuid(req.id)
        if automation_id not in self.automations:
            raise NotFoundError(f"Automation {automation_id} not found")
        self.automations[automation_id] = req
        return req

    def GetAutomation(self, req: UUIDMessage) -> AutomationPrototypeMessage:  # noqa: N802
        automation_id = uuid_message_to_uuid(req)
        if automation_id in self.automations:
            return self.automations[automation_id]
        raise NotFoundError(f"Automation {automation_id} not found")

    def DeleteAutomation(self, req: DeleteAutomationRequest) -> None:  # noqa: N802
        automation_id = uuid_message_to_uuid(req.automation_id)
        if automation_id in self.automations:
            del self.automations[automation_id]
        else:
            raise NotFoundError(f"Automation {automation_id} not found")

    def ListAutomations(self, req: Empty) -> Automations:  # noqa: N802
        _ = req
        return Automations(automations=list(self.automations.values()))


class AutomationCRUDOperations(RuleBasedStateMachine):
    """
    A state machine that tests the CRUD operations of the Automations client.

    The rules defined here will be executed in random order by Hypothesis, and each rule can be called any number of
    times. The state of the state machine is defined by the bundles, which are collections of objects that can be
    inserted into the state machine by the rules. Rules can also consume objects from the bundles, which will remove
    them from the state machine state.

    For more information see:
    https://hypothesis.readthedocs.io/en/latest/stateful.html
    """

    def __init__(self) -> None:
        super().__init__()
        service = AutomationService(MagicMock())
        service.service = MockAutomationService()  # mock the gRPC service
        self.client = AutomationClient(service)
        self.count_automations = 0

    inserted_automations: Bundle[AutomationPrototype] = Bundle("automations")

    @rule(
        target=inserted_automations,
        task_name=alphanumerical_text(min_size=4, max_size=50),
        cluster_slug=alphanumerical_text(min_size=4, max_size=20),
        task_identifier=task_identifiers(),
        cron_triggers=lists(cron_triggers(), min_size=1, max_size=10),
    )
    def create_cron_automation(
        self,
        task_name: str,
        cluster_slug: str,
        task_identifier: TaskIdentifier,
        cron_triggers: list[CronTrigger],
    ) -> AutomationPrototype:
        self.count_automations += 1
        schedules = [t.schedule for t in cron_triggers]

        class TestCronTask(CronTask):
            some_arg: str

            @staticmethod
            def identifier() -> tuple[str, str]:
                return task_identifier.name, task_identifier.version

        task = TestCronTask(task_name)  # task_name reused to serialize the task input

        return self.client.create_cron_automation(task_name, task, schedules, cluster_slug)

    @rule(
        target=inserted_automations,
        task_name=alphanumerical_text(min_size=4, max_size=50),
        cluster_slug=alphanumerical_text(min_size=4, max_size=20),
        task_identifier=task_identifiers(),
        storage_event_triggers=lists(storage_event_triggers(), min_size=1, max_size=10),
    )
    def create_storage_event_automation(
        self,
        task_name: str,
        cluster_slug: str,
        task_identifier: TaskIdentifier,
        storage_event_triggers: list[StorageEventTrigger],
    ) -> AutomationPrototype:
        self.count_automations += 1
        triggers = [(t.storage_location, t.glob_pattern) for t in storage_event_triggers]

        class TestStorageEventTask(StorageEventTask):
            some_arg: str

            @staticmethod
            def identifier() -> tuple[str, str]:
                return task_identifier.name, task_identifier.version

        task = TestStorageEventTask(task_name)  # task_name reused to serialize the task input

        return self.client.create_storage_event_automation(task_name, task, triggers, cluster_slug)

    @rule(automation=inserted_automations)
    def get_automation(self, automation: AutomationPrototype) -> None:
        got = self.client.find(automation.id)
        assert automation.id == got.id
        assert automation.name == got.name

    @rule(automation=consumes(inserted_automations))  # consumes -> remove from bundle afterwards
    def delete_automation(self, automation: AutomationPrototype) -> None:
        self.count_automations -= 1
        self.client.delete(automation)

    @rule()
    def list_automations(self) -> None:
        automations = self.client.all()
        assert len(automations) == self.count_automations


# make pytest pick up the test cases from the state machine
TestAutomationCRUDOperations = AutomationCRUDOperations.TestCase
