import builtins
from typing import Any
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
from tilebox.workflows.workflows.v1.automation_pb2 import Automations, DeleteAutomationRequest
from tilebox.workflows.workflows.v1.automation_pb2_grpc import AutomationServiceStub
from tilebox.workflows.workflows.v1.storage_location_pb2 import StorageLocations
from tilebox.workflows.workflows.v1.storage_location_pb2_grpc import StorageLocationServiceStub


class AutomationService:
    def __init__(self, channel: Channel | Any, storage_channel: Channel | Any = None) -> None:
        """
        A wrapper around the AutomationServiceStub that provides a more pythonic interface and converts the protobuf
        messages to and from the data classes used in the rest of the tilebox-workflows codebase.

        Args:
            channel: The gRPC channel to use for the service.
            storage_channel: Optional separate storage-location client for the Connect transport.
        """
        self.service = (
            with_pythonic_errors(AutomationServiceStub(channel)) if hasattr(channel, "unary_unary") else channel
        )
        if storage_channel is None:
            storage_channel = channel
        self.storage_service = (
            with_pythonic_errors(StorageLocationServiceStub(storage_channel))
            if hasattr(storage_channel, "unary_unary")
            else storage_channel
        )

    def list_storage_locations(self) -> builtins.list[StorageLocation]:
        response: StorageLocations = self.storage_service.ListStorageLocations(Empty())
        return [StorageLocation.from_message(sl) for sl in response.locations]

    def list(self) -> builtins.list[AutomationPrototype]:
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
