from uuid import UUID

from google.protobuf.empty_pb2 import Empty
from grpc import Channel

from _tilebox.grpc.error import with_pythonic_errors
from tilebox.datasets.uuid import uuid_to_uuid_message
from tilebox.workflows.data import (
    AutomationPrototype,
    StorageLocation,
)
from tilebox.workflows.workflows.v1.automation_pb2 import AutomationPrototype as AutomationPrototypeMessage
from tilebox.workflows.workflows.v1.automation_pb2 import Automations, DeleteAutomationRequest, StorageLocations
from tilebox.workflows.workflows.v1.automation_pb2_grpc import AutomationServiceStub


class AutomationService:
    def __init__(self, channel: Channel) -> None:
        """
        A wrapper around the AutomationServiceStub that provides a more pythonic interface and converts the protobuf
        messages to and from the data classes used in the rest of the tilebox-workflows codebase.

        Args:
            channel: The gRPC channel to use for the service.
        """
        self.service = with_pythonic_errors(AutomationServiceStub(channel))

    def list_storage_locations(self) -> list[StorageLocation]:
        response: StorageLocations = self.service.ListStorageLocations(Empty())
        return [StorageLocation.from_message(sl) for sl in response.locations]

    def list(self) -> list[AutomationPrototype]:
        response: Automations = self.service.ListAutomations(Empty())
        return [AutomationPrototype.from_message(automation) for automation in response.automations]

    def get_by_id(self, automation_id: UUID) -> AutomationPrototype:
        response: AutomationPrototypeMessage = self.service.GetAutomation(uuid_to_uuid_message(automation_id))
        return AutomationPrototype.from_message(response)

    def create(self, automation: AutomationPrototype) -> AutomationPrototype:
        response: AutomationPrototypeMessage = self.service.CreateAutomation(automation.to_message())
        return AutomationPrototype.from_message(response)

    def update(self, automation: AutomationPrototype) -> AutomationPrototype:
        response: AutomationPrototypeMessage = self.service.UpdateAutomation(automation.to_message())
        return AutomationPrototype.from_message(response)

    def delete(self, automation_id: UUID, cancel_jobs: bool = False) -> None:
        self.service.DeleteAutomation(
            DeleteAutomationRequest(automation_id=uuid_to_uuid_message(automation_id), cancel_jobs=cancel_jobs)
        )
