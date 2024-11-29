from uuid import UUID

from google.protobuf.empty_pb2 import Empty
from grpc import Channel

from _tilebox.grpc.error import with_pythonic_errors
from tilebox.workflows.data import (
    RecurrentTaskPrototype,
    StorageLocation,
    uuid_to_uuid_message,
)
from tilebox.workflows.workflowsv1.recurrent_task_pb2 import RecurrentTaskPrototype as RecurrentTaskPrototypeMessage
from tilebox.workflows.workflowsv1.recurrent_task_pb2 import RecurrentTasks, StorageLocations
from tilebox.workflows.workflowsv1.recurrent_task_pb2_grpc import RecurrentTaskServiceStub


class RecurrentTaskService:
    def __init__(self, channel: Channel) -> None:
        """
        A wrapper around the RecurrentTaskServiceStub that provides a more pythonic interface and converts the protobuf
        messages to and from the data classes used in the rest of the tilebox-workflows codebase.

        Args:
            channel: The gRPC channel to use for the service.
        """
        self.service = with_pythonic_errors(RecurrentTaskServiceStub(channel))

    def list_storage_locations(self) -> list[StorageLocation]:
        response: StorageLocations = self.service.ListStorageLocations(Empty())
        return [StorageLocation.from_message(sl) for sl in response.locations]

    def list(self) -> list[RecurrentTaskPrototype]:
        response: RecurrentTasks = self.service.ListRecurrentTasks(Empty())
        return [RecurrentTaskPrototype.from_message(task) for task in response.tasks]

    def get_by_id(self, task_id: UUID) -> RecurrentTaskPrototype:
        response: RecurrentTaskPrototypeMessage = self.service.GetRecurrentTask(uuid_to_uuid_message(task_id))
        return RecurrentTaskPrototype.from_message(response)

    def create(self, task: RecurrentTaskPrototype) -> RecurrentTaskPrototype:
        response: RecurrentTaskPrototypeMessage = self.service.CreateRecurrentTask(task.to_message())
        return RecurrentTaskPrototype.from_message(response)

    def update(self, task: RecurrentTaskPrototype) -> RecurrentTaskPrototype:
        response: RecurrentTaskPrototypeMessage = self.service.UpdateRecurrentTask(task.to_message())
        return RecurrentTaskPrototype.from_message(response)

    def delete(self, task_id: UUID) -> None:
        self.service.DeleteRecurrentTask(uuid_to_uuid_message(task_id))
