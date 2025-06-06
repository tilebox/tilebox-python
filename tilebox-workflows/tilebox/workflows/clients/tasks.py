from uuid import UUID

from google.protobuf.duration_pb2 import Duration
from grpc.aio import Channel

from tilebox.workflows.data import (
    ComputedTask,
    NextTaskToRun,
    Task,
    TaskLease,
    uuid_to_uuid_message,
)
from tilebox.workflows.workflowsv1.core_pb2 import TaskLease as TaskLeaseMessage
from tilebox.workflows.workflowsv1.task_pb2 import (
    NextTaskRequest,
    NextTaskResponse,
    TaskFailedRequest,
    TaskLeaseRequest,
)
from tilebox.workflows.workflowsv1.task_pb2_grpc import TaskServiceStub


class TaskService:
    def __init__(self, channel: Channel) -> None:
        """
        A wrapper around the TaskServiceStub that provides a more pythonic interface and converts the protobuf messages
        to and from the data classes used in the rest of the tilebox-workflows codebase.

        Args:
            channel: The gRPC channel to use for the service.
        """
        self.service = TaskServiceStub(channel)

    async def next_task(self, task_to_run: NextTaskToRun | None, computed_task: ComputedTask | None) -> Task | None:
        """Mark a task as computed and ask for the next task to run.

        Args:
            task_to_run: The tasks that the current task runner making this request is able to run. If not set, a
                next task to run will never be returned.
            computed_task: The task that was just computed, and to be marked as such in the workflows service.
                If None, no task will be marked as computed, but a next task to run may still be returned.
                (work-stealing)

        Returns:
            The next task to run, or None if there are no tasks to run.
        """
        computed_task_message = None if computed_task is None else computed_task.to_message()
        task_to_run_message = None if task_to_run is None else task_to_run.to_message()

        response: NextTaskResponse = await self.service.NextTask(
            NextTaskRequest(computed_task=computed_task_message, next_task_to_run=task_to_run_message)
        )
        return (
            Task.from_message(response.next_task)
            if response.next_task is not None and response.next_task.id.uuid
            else None
        )

    async def task_failed(self, task: Task, error: Exception, cancel_job: bool = True) -> None:
        """Mark a task as failed.

        Args:
            task: The task that failed.
            error: The error / exception that occurred.
            cancel_job: Whether to cancel the whole job that the task belongs to.
        """
        # job ouptut is limited to 1KB, so truncate the error message if necessary
        error_message = repr(error)[:1024]
        display = f"{task.display}" if error_message == "" else f"{task.display}\n{error_message}"

        request = TaskFailedRequest(task_id=uuid_to_uuid_message(task.id), cancel_job=cancel_job, display=display)
        await self.service.TaskFailed(request)

    async def extend_task_lease(self, task_id: UUID, requested_lease: int) -> TaskLease:
        """Extend the lease of a task.

        Args:
            task_id: The UUID of the task to extend the lease for.
            requested_lease: The requested lease duration in seconds.

        Returns:
            The new lease details for the task.
        """
        request = TaskLeaseRequest(
            task_id=uuid_to_uuid_message(task_id), requested_lease=Duration(seconds=requested_lease)
        )
        response: TaskLeaseMessage = await self.service.ExtendTaskLease(request)
        return TaskLease.from_message(response)
