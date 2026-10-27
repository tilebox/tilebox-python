from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest
from hypothesis.stateful import Bundle, RuleBasedStateMachine, consumes, rule
from hypothesis.strategies import lists
from protobuf.wkt.google.protobuf.empty_pb import Empty
from tests.tasks_data import alphanumerical_text, cron_triggers, storage_event_triggers, task_identifiers

from _tilebox.errors import NotFoundError
from _tilebox.proto.tilebox.v1.id_pb import ID
from tilebox.datasets.uuid import uuid_message_to_uuid
from tilebox.workflows.automations import CronTask, StorageEventTask
from tilebox.workflows.automations.client import AutomationClient
from tilebox.workflows.data import (
    AutomationPrototype,
    CronTrigger,
    StorageEventTrigger,
    StorageLocation,
    StorageType,
    TaskIdentifier,
    Workflow,
    uuid_to_uuid_message,
)
from tilebox.workflows.v1.automation_connect import AutomationServiceClientSync
from tilebox.workflows.v1.automation_pb import AutomationPrototype as AutomationPrototypeMessage
from tilebox.workflows.v1.automation_pb import Automations, DeleteAutomationRequest
from tilebox.workflows.v1.automation_pb import CronTrigger as CronTriggerMessage
from tilebox.workflows.v1.automation_pb import StorageEventTrigger as StorageEventTriggerMessage
from tilebox.workflows.v1.workflows_connect import WorkflowsServiceClientSync
from tilebox.workflows.v1.workflows_pb import GetWorkflowRequest
from tilebox.workflows.v1.workflows_pb import Workflow as WorkflowMessage


class MockAutomationService:
    """Store automations in memory for client behavior tests."""

    def __init__(self) -> None:
        self.automations: dict[UUID, AutomationPrototypeMessage] = {}

    def create_automation(self, req: AutomationPrototypeMessage) -> AutomationPrototypeMessage:
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

    def update_automation(self, req: AutomationPrototypeMessage) -> AutomationPrototypeMessage:
        automation_id = uuid_message_to_uuid(req.id)
        if automation_id not in self.automations:
            raise NotFoundError(f"Automation {automation_id} not found")
        self.automations[automation_id] = req
        return req

    def get_automation(self, req: ID) -> AutomationPrototypeMessage:
        automation_id = uuid_message_to_uuid(req)
        if automation_id in self.automations:
            return self.automations[automation_id]
        raise NotFoundError(f"Automation {automation_id} not found")

    def delete_automation(self, req: DeleteAutomationRequest) -> None:
        automation_id = uuid_message_to_uuid(req.automation_id)
        if automation_id in self.automations:
            del self.automations[automation_id]
        else:
            raise NotFoundError(f"Automation {automation_id} not found")

    def list_automations(self, req: Empty) -> Automations:
        _ = req
        return Automations(automations=list(self.automations.values()))


@pytest.mark.parametrize("kind", ["cron", "storage"])
@pytest.mark.parametrize("selection", ["reference", "object", "unscoped"])
def test_automation_scope_survives_creation_and_reads(kind: str, selection: str) -> None:
    class ScheduledTask(CronTask):
        pass

    class StorageTask(StorageEventTask):
        pass

    workflow = Workflow("owner:workflow-123", "Workflow", "", id=uuid4(), project_slug="workflow")

    def find(request: GetWorkflowRequest) -> WorkflowMessage:
        if request.workflow_reference != workflow.reference:
            raise NotFoundError("Workflow not found")
        return workflow.to_message()

    workflow_service = MagicMock(spec=WorkflowsServiceClientSync)
    workflow_service.get_workflow.side_effect = find
    mock_service = MockAutomationService()
    client = AutomationClient(MagicMock(spec=AutomationServiceClientSync, wraps=mock_service), workflow_service)
    selected = workflow.reference if selection == "reference" else workflow if selection == "object" else None
    if kind == "cron":
        created = client.create_cron_automation("Scheduled", ScheduledTask(), "0 * * * *", workflow=selected)
    else:
        storage = StorageLocation(uuid4(), "test-bucket", StorageType.AWS_S3)
        created = client.create_storage_event_automation(
            "Storage", StorageTask(), (storage, "*.tif"), workflow=selected
        )
    expected = workflow.id if selected is not None else None
    assert created.prototype.identifier.workflow_id == expected
    assert client.find(created.id).prototype.identifier.workflow_id == expected
    assert client.all()[0].prototype.identifier.workflow_id == expected
    stored = mock_service.automations[created.id].prototype
    assert stored is not None
    assert stored.identifier is not None
    assert stored.identifier.workflow_id == uuid_to_uuid_message(expected)


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
        service = MagicMock(spec=AutomationServiceClientSync, wraps=MockAutomationService())
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
