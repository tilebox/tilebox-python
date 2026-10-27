from typing import Any
from uuid import UUID

from protobuf.wkt.google.protobuf.duration_pb import Duration

from _tilebox.client import Connection
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
from tilebox.workflows.v1.core_pb import TaskLease as TaskLeaseMessage
from tilebox.workflows.v1.task_connect import TaskServiceClientSync
from tilebox.workflows.v1.task_pb import (
    NextTaskRequest,
    NextTaskResponse,
    TaskLeaseRequest,
)


class TaskService:
    def __init__(self, channel: Connection | Any) -> None:
        """Wrap a native synchronous task client or construct one from a shared connection."""
        self.service = channel.client(TaskServiceClientSync) if isinstance(channel, Connection) else channel

    def next_task(self, task_to_run: NextTaskToRun | None, computed_task: ComputedTask | None) -> Task | Idling | None:
        computed_task_message = None if computed_task is None else computed_task.to_message()
        task_to_run_message = None if task_to_run is None else task_to_run.to_message()

        response: NextTaskResponse = self.service.next_task(
            NextTaskRequest(computed_task=computed_task_message, next_task_to_run=task_to_run_message)
        )

        if response.next_task is not None and response.next_task.id is not None and response.next_task.id.uuid:
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
        self.service.task_failed(request)

    def extend_task_lease(self, task_id: UUID, requested_lease: int) -> TaskLease:
        request = TaskLeaseRequest(
            task_id=uuid_to_uuid_message(task_id), requested_lease=Duration(seconds=requested_lease)
        )
        response: TaskLeaseMessage = self.service.extend_task_lease(request)
        return TaskLease.from_message(response)
