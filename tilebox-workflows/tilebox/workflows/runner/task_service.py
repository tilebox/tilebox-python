from uuid import UUID

from google.protobuf.duration_pb2 import Duration
from grpc import Channel

from _tilebox.grpc.error import with_pythonic_errors
from tilebox.workflows.data import (
    ComputedTask,
    FailedTask,
    Idling,
    NextTaskToRun,
    ProgressIndicator,
    Task,
    TaskLease,
    uuid_to_uuid_message,
)
from tilebox.workflows.workflows.v1.core_pb2 import TaskLease as TaskLeaseMessage
from tilebox.workflows.workflows.v1.task_pb2 import (
    NextTaskRequest,
    NextTaskResponse,
    TaskLeaseRequest,
)
from tilebox.workflows.workflows.v1.task_pb2_grpc import TaskServiceStub


class TaskService:
    def __init__(self, channel: Channel) -> None:
        """
        A wrapper around the TaskServiceStub that provides a more pythonic interface and converts the protobuf messages
        to and from the data classes used in the rest of the tilebox-workflows codebase.

        Args:
            channel: The gRPC channel to use for the service.
        """
        self.service = with_pythonic_errors(TaskServiceStub(channel))

    def next_task(self, task_to_run: NextTaskToRun | None, computed_task: ComputedTask | None) -> Task | Idling | None:
        computed_task_message = None if computed_task is None else computed_task.to_message()
        task_to_run_message = None if task_to_run is None else task_to_run.to_message()

        response: NextTaskResponse = self.service.NextTask(
            NextTaskRequest(computed_task=computed_task_message, next_task_to_run=task_to_run_message)
        )

        if response.next_task is not None and response.next_task.id.uuid:
            return Task.from_message(response.next_task)
        if response.idling is not None:
            return Idling.from_message(response.idling)
        return None

    def task_failed(
        self,
        task: Task | FailedTask,
        error: Exception | None = None,
        was_workflow_error: bool | None = None,
        progress_updates: list[ProgressIndicator] | None = None,
    ) -> None:
        if isinstance(task, FailedTask):
            request = task.to_message()
        else:
            if error is None or was_workflow_error is None or progress_updates is None:
                raise ValueError("error, was_workflow_error, and progress_updates are required when passing a Task")
            request = FailedTask.from_task_error(task, error, was_workflow_error, progress_updates).to_message()
        self.service.TaskFailed(request)

    def extend_task_lease(self, task_id: UUID, requested_lease: int) -> TaskLease:
        request = TaskLeaseRequest(
            task_id=uuid_to_uuid_message(task_id), requested_lease=Duration(seconds=requested_lease)
        )
        response: TaskLeaseMessage = self.service.ExtendTaskLease(request)
        return TaskLease.from_message(response)
