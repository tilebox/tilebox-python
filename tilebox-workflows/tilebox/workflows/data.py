import re
import warnings
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from functools import lru_cache
from pathlib import Path
from uuid import UUID

import boto3
from google.cloud.storage import Client as GoogleStorageClient
from google.cloud.storage.bucket import Bucket
from google.protobuf.duration_pb2 import Duration

from tilebox.datasets.query.id_interval import IDInterval
from tilebox.datasets.query.pagination import Pagination
from tilebox.datasets.query.time_interval import TimeInterval, datetime_to_timestamp, timestamp_to_datetime
from tilebox.datasets.uuid import uuid_message_to_optional_uuid, uuid_message_to_uuid, uuid_to_uuid_message

try:
    # let's not make this a hard dependency, but if it's installed we can use its types
    from mypy_boto3_s3.client import S3Client
except ModuleNotFoundError:
    from typing import Any as S3Client
from opentelemetry.trace import ProxyTracerProvider, Tracer

from tilebox.datasets.sync.client import Client as DatasetsClient
from tilebox.workflows.workflows.v1 import automation_pb2 as automation_pb
from tilebox.workflows.workflows.v1 import core_pb2, job_pb2, task_pb2

_VERSION_PATTERN = re.compile(r"^v(\d+)\.(\d+)$")  # matches a version string in the format "v3.2"


class TaskState(Enum):
    UNSPECIFIED = 0
    QUEUED = 1
    RUNNING = 2
    COMPUTED = 3
    FAILED = 4
    CANCELLED = 5


_TASK_STATES = {state.value: state for state in TaskState}


@dataclass(order=True, eq=True, unsafe_hash=True, frozen=True)
class TaskIdentifier:
    name: str
    version: str

    @classmethod  # lets use typing.Self once we require python >= 3.11
    def from_message(cls, identifier: core_pb2.TaskIdentifier) -> "TaskIdentifier":
        return cls(name=identifier.name, version=identifier.version)

    def to_message(self) -> core_pb2.TaskIdentifier:
        return core_pb2.TaskIdentifier(name=self.name, version=self.version)

    @classmethod
    def from_name_and_version(cls, name: str, version: str) -> "TaskIdentifier":
        """
        Construct a TaskIdentifier object from a task name and version, and perform some client-side validation
        on those values.

        Args:
            name: The task name
            version: The task version in the format "vMajor.Minor", e.g. v3.2

        Raises:
            ValueError: If the task name is empty or the version string is invalid.

        Returns:
            Task metadata
        """
        if name == "":
            raise ValueError("A task name is required")
        if len(name) > 256:
            raise ValueError("The task name is too long")

        _parse_version(version)  # validate the version string
        return cls(name=name, version=version)


@dataclass
class TaskLease:
    lease: int
    recommended_wait_until_next_extension: int

    @classmethod
    def from_message(cls, computed_task: core_pb2.TaskLease) -> "TaskLease":
        """Convert a TaskLease protobuf message to a TaskLease object."""
        return cls(
            lease=computed_task.lease.ToSeconds(),
            recommended_wait_until_next_extension=computed_task.recommended_wait_until_next_extension.ToSeconds(),
        )

    def to_message(self) -> core_pb2.TaskLease:
        """Convert a TaskLease object to a TaskLease protobuf message."""
        return core_pb2.TaskLease(
            lease=Duration(seconds=self.lease),
            recommended_wait_until_next_extension=Duration(seconds=self.recommended_wait_until_next_extension),
        )


@dataclass(order=True)
class Task:
    id: UUID
    identifier: TaskIdentifier
    state: TaskState = field(default=TaskState.QUEUED)
    input: bytes = field(default=b"")
    display: str | None = field(default=None)
    job: "Job | None" = field(default=None)
    parent_id: UUID | None = field(default=None)
    depends_on: list[UUID] = field(default_factory=list)
    lease: TaskLease | None = field(default=None)
    retry_count: int = field(default=0)

    @classmethod
    def from_message(cls, task: core_pb2.Task) -> "Task":  # lets use typing.Self once we require python >= 3.11
        """Convert a Task protobuf message to a Task object."""
        return cls(
            id=uuid_message_to_uuid(task.id),
            identifier=TaskIdentifier.from_message(task.identifier),
            state=_TASK_STATES[task.state],
            input=task.input,
            display=task.display,
            job=Job.from_message(task.job) if task.job else None,
            parent_id=uuid_message_to_uuid(task.parent_id) if task.parent_id.uuid else None,
            depends_on=[uuid_message_to_uuid(uuid) for uuid in task.depends_on],
            lease=TaskLease.from_message(task.lease) if task.lease else None,
            retry_count=task.retry_count,
        )

    def to_message(self) -> core_pb2.Task:
        """Convert a Task object to a Task protobuf message."""
        depends_on = [uuid_to_uuid_message(uuid) for uuid in self.depends_on]
        depends_on_valid = [uuid for uuid in depends_on if uuid is not None]

        return core_pb2.Task(
            id=uuid_to_uuid_message(self.id),
            identifier=self.identifier.to_message(),
            state=f"TASK_STATE_{self.state.name}",
            input=self.input,
            display=self.display,
            job=self.job.to_message() if self.job else None,
            parent_id=uuid_to_uuid_message(self.parent_id) if self.parent_id else None,
            depends_on=depends_on_valid,
            lease=self.lease.to_message() if self.lease else None,
            retry_count=self.retry_count,
        )


class JobState(Enum):
    UNSPECIFIED = 0
    QUEUED = 1
    STARTED = 2
    COMPLETED = 3


_JOB_STATES = {state.value: state for state in JobState}


@dataclass(order=True)
class Job:
    id: UUID
    name: str
    trace_parent: str
    state: JobState
    canceled: bool

    @classmethod
    def from_message(cls, job: core_pb2.Job) -> "Job":  # lets use typing.Self once we require python >= 3.11
        """Convert a Job protobuf message to a Job object."""
        return cls(
            id=uuid_message_to_uuid(job.id),
            name=job.name,
            trace_parent=job.trace_parent,
            state=_JOB_STATES[job.state],
            canceled=job.canceled,
        )

    def to_message(self) -> core_pb2.Job:
        """Convert a Job object to a Job protobuf message."""
        return core_pb2.Job(
            id=uuid_to_uuid_message(self.id),
            name=self.name,
            trace_parent=self.trace_parent,
            state=f"JOB_STATE_{self.state.name}",
            canceled=self.canceled,
        )


@dataclass(order=True)
class Cluster:
    slug: str
    display_name: str
    deletable: bool

    @classmethod  # lets use typing.Self once we require python >= 3.11
    def from_message(cls, cluster: core_pb2.Cluster) -> "Cluster":
        """Convert a Cluster protobuf message to a Cluster object."""
        return cls(slug=cluster.slug, display_name=cluster.display_name, deletable=cluster.deletable)

    def to_message(self) -> core_pb2.Cluster:
        """Convert a Cluster object to a Cluster protobuf message."""
        return core_pb2.Cluster(slug=self.slug, display_name=self.display_name, deletable=self.deletable)


@dataclass
class NextTaskToRun:
    cluster_slug: str
    identifiers: dict[TaskIdentifier, type]

    # from message not needed, as we never return this from the server

    def to_message(self) -> task_pb2.NextTaskToRun:
        """Convert a NextTaskToRun object to a NextTaskToRun protobuf message."""
        return task_pb2.NextTaskToRun(
            cluster_slug=self.cluster_slug,
            identifiers=[identifier.to_message() for identifier in self.identifiers],
        )


@dataclass
class TaskSubmission:
    cluster_slug: str
    identifier: TaskIdentifier
    input: bytes
    dependencies: list[int]
    display: str
    max_retries: int = 0

    @classmethod
    def from_message(cls, sub_task: core_pb2.TaskSubmission) -> "TaskSubmission":
        """Convert a TaskSubmission protobuf message to a TaskSubmission object."""
        return cls(
            cluster_slug=sub_task.cluster_slug,
            identifier=TaskIdentifier.from_message(sub_task.identifier),
            input=sub_task.input,
            dependencies=list(sub_task.dependencies),
            display=sub_task.display,
            max_retries=sub_task.max_retries,
        )

    def to_message(self) -> core_pb2.TaskSubmission:
        """Convert a TaskSubmission object to a TaskSubmission protobuf message."""
        return core_pb2.TaskSubmission(
            cluster_slug=self.cluster_slug,
            identifier=self.identifier.to_message(),
            input=self.input,
            dependencies=self.dependencies,
            display=self.display,
            max_retries=self.max_retries,
        )


@dataclass
class ComputedTask:
    id: UUID
    display: str | None
    sub_tasks: list[TaskSubmission]

    @classmethod
    def from_message(cls, computed_task: task_pb2.ComputedTask) -> "ComputedTask":
        """Convert a ComputedTask protobuf message to a ComputedTask object."""
        return cls(
            id=uuid_message_to_uuid(computed_task.id),
            display=computed_task.display,
            sub_tasks=[TaskSubmission.from_message(sub_task) for sub_task in computed_task.sub_tasks],
        )

    def to_message(self) -> task_pb2.ComputedTask:
        """Convert a ComputedTask object to a ComputedTask protobuf message."""
        return task_pb2.ComputedTask(
            id=uuid_to_uuid_message(self.id),
            display=self.display,
            sub_tasks=[sub_task.to_message() for sub_task in self.sub_tasks],
        )


def _parse_version(version: str) -> tuple[int, int]:
    """
    Parse the major and minor version from a string in the format "vMajor.Minor" and returns them as tuple of ints.

    Args:
        version: The version string to parse.

    Returns:
        Tuple of major and minor version.
    """
    if match := _VERSION_PATTERN.match(version):
        return int(match.group(1)), int(match.group(2))

    raise ValueError(f"Invalid version string: {version}")


class StorageType(Enum):
    GCS = automation_pb.STORAGE_TYPE_GCS  # Google Cloud Storage
    S3 = automation_pb.STORAGE_TYPE_S3  # Amazon Web Services S3
    FS = automation_pb.STORAGE_TYPE_FS  # Local Filesystem


_STORAGE_TYPE_TO_ENUM = {storage_type.value: storage_type for storage_type in StorageType}


@dataclass(frozen=True, order=True)
class StorageLocation:
    id: UUID
    location: str
    type: StorageType
    runner_context: "RunnerContext | None" = None

    @classmethod  # lets use typing.Self once we require python >= 3.11
    def from_message(cls, storage_location: automation_pb.StorageLocation) -> "StorageLocation":
        """Convert a StorageLocation protobuf message to a StorageLocation object."""
        return cls(
            id=uuid_message_to_uuid(storage_location.id),
            location=storage_location.location,
            type=_STORAGE_TYPE_TO_ENUM[storage_location.type],
        )

    def _with_runner_context(self, runner_context: "RunnerContext") -> "StorageLocation":
        return StorageLocation(
            id=self.id,
            location=self.location,
            type=self.type,
            runner_context=runner_context,
        )

    def to_message(self) -> automation_pb.StorageLocation:
        """Convert a StorageLocation object to a StorageLocation protobuf message."""
        return automation_pb.StorageLocation(
            id=uuid_to_uuid_message(self.id), location=self.location, type=self.type.value
        )

    def read(self, path: str) -> bytes:
        runner_context = self.runner_context or RunnerContext()

        match self.type:
            case StorageType.GCS:
                with runner_context.tracer.start_as_current_span("gcs.read") as span:
                    span.set_attribute("bucket", self.location)
                    span.set_attribute("path", path)
                    # GCS library has some weird typing issues, so let's ignore them for now
                    blob = runner_context.gcs_client(self.location).blob(path)  # type: ignore[arg-type]
                    return blob.download_as_bytes()  # type: ignore[arg-type]
            case StorageType.S3:
                with runner_context.tracer.start_as_current_span("s3.read") as span:
                    span.set_attribute("bucket", self.location)
                    span.set_attribute("path", path)
                return runner_context.s3_client(self.location).get_object(Bucket=self.location, Key=path)["Body"].read()
            case StorageType.FS:
                with runner_context.tracer.start_as_current_span("fs.read") as span:
                    span.set_attribute("root_directory", self.location)
                    span.set_attribute("path", path)
                return Path(self.location).joinpath(path).read_bytes()


@dataclass(order=True)
class StorageEventTrigger:
    id: UUID
    storage_location: StorageLocation
    glob_pattern: str

    @classmethod
    def from_message(cls, trigger: automation_pb.StorageEventTrigger) -> "StorageEventTrigger":
        """Convert a StorageEventTrigger protobuf message to a StorageEventTrigger object."""
        return cls(
            id=uuid_message_to_uuid(trigger.id),
            storage_location=StorageLocation.from_message(trigger.storage_location),
            glob_pattern=trigger.glob_pattern,
        )

    def to_message(self) -> automation_pb.StorageEventTrigger:
        """Convert a StorageEventTrigger object to a StorageEventTrigger protobuf message."""
        return automation_pb.StorageEventTrigger(
            id=uuid_to_uuid_message(self.id),
            storage_location=self.storage_location.to_message(),
            glob_pattern=self.glob_pattern,
        )


class StorageEventType(Enum):
    CREATED = automation_pb.STORAGE_EVENT_TYPE_CREATED


_STORAGE_EVENT_TYPE_TO_ENUM = {storage_event_type.value: storage_event_type for storage_event_type in StorageEventType}


@dataclass(order=True)
class TriggeredStorageEvent:
    storage: StorageLocation
    type: StorageEventType
    location: str

    @classmethod
    def from_message(
        cls, event: automation_pb.TriggeredStorageEvent, locations: dict[UUID, StorageLocation]
    ) -> "TriggeredStorageEvent":
        """Convert a TriggeredStorageEvent protobuf message to a TriggeredStorageEvent object."""
        storage_location_id = uuid_message_to_uuid(event.storage_location_id)

        try:
            location = locations[storage_location_id]
        except KeyError:
            raise ValueError(f"Storage location with id {storage_location_id} is unknown.") from None

        return cls(
            storage=location,
            type=_STORAGE_EVENT_TYPE_TO_ENUM[event.type],
            location=event.location,
        )

    def to_message(self) -> automation_pb.TriggeredStorageEvent:
        """Convert a TriggeredStorageEvent object to a TriggeredStorageEvent protobuf message."""
        return automation_pb.TriggeredStorageEvent(
            storage_location_id=uuid_to_uuid_message(self.storage.id),
            type=self.type.value,
            location=self.location,
        )


@dataclass(order=True)
class CronTrigger:
    id: UUID
    schedule: str

    @classmethod
    def from_message(cls, trigger: automation_pb.CronTrigger) -> "CronTrigger":
        """Convert a CronTrigger protobuf message to a CronTrigger object."""
        return cls(id=uuid_message_to_uuid(trigger.id), schedule=trigger.schedule)

    def to_message(self) -> automation_pb.CronTrigger:
        """Convert a CronTrigger object to a CronTrigger protobuf message."""
        return automation_pb.CronTrigger(id=uuid_to_uuid_message(self.id), schedule=self.schedule)


@dataclass(order=True)
class TriggeredCronEvent:
    time: datetime

    @classmethod
    def from_message(cls, event: automation_pb.TriggeredCronEvent) -> "TriggeredCronEvent":
        """Convert a TriggeredCronEvent protobuf message to a TriggeredCronEvent object."""
        return cls(time=timestamp_to_datetime(event.trigger_time))

    def to_message(self) -> automation_pb.TriggeredCronEvent:
        """Convert a TriggeredCronEvent object to a TriggeredCronEvent protobuf message."""
        return automation_pb.TriggeredCronEvent(trigger_time=datetime_to_timestamp(self.time))


@dataclass(order=True)
class AutomationPrototype:
    id: UUID
    name: str
    prototype: TaskSubmission
    storage_event_triggers: list[StorageEventTrigger]
    cron_triggers: list[CronTrigger]

    @classmethod
    def from_message(cls, task: automation_pb.AutomationPrototype) -> "AutomationPrototype":
        """Convert a AutomationPrototype protobuf message to a AutomationPrototype object."""
        return cls(
            id=uuid_message_to_uuid(task.id),
            name=task.name,
            prototype=TaskSubmission.from_message(task.prototype),
            storage_event_triggers=[
                StorageEventTrigger.from_message(trigger) for trigger in task.storage_event_triggers
            ],
            cron_triggers=[CronTrigger.from_message(trigger) for trigger in task.cron_triggers],
        )

    def to_message(self) -> automation_pb.AutomationPrototype:
        """Convert a AutomationPrototype object to a AutomationPrototype protobuf message."""
        return automation_pb.AutomationPrototype(
            id=uuid_to_uuid_message(self.id),
            name=self.name,
            prototype=self.prototype.to_message(),
            storage_event_triggers=[trigger.to_message() for trigger in self.storage_event_triggers],
            cron_triggers=[trigger.to_message() for trigger in self.cron_triggers],
        )


class RunnerContext:
    def __init__(
        self,
        tracer: Tracer | None = None,
        datasets_client: DatasetsClient | None = None,
        storage_locations: list[StorageLocation] | None = None,
    ) -> None:
        if tracer is None:
            self.tracer = ProxyTracerProvider().get_tracer("tilebox.workflows.RunnerContext")
        else:
            self.tracer = tracer
        self.datasets_client = datasets_client
        self.storage_locations = {
            sl.id: sl._with_runner_context(self)  # noqa: SLF001
            for sl in storage_locations or []
        }

    def gcs_client(self, location: str) -> Bucket:
        return _default_google_storage_client(location)

    def s3_client(self, location: str) -> S3Client:
        _ = location  # we always use the default s3 client, regardless of the location
        with warnings.catch_warnings():
            # https://github.com/boto/boto3/issues/3889
            warnings.filterwarnings("ignore", category=DeprecationWarning, message=".*datetime.utcnow.*")
            return boto3.client("s3")

    def local_path(self, location: str) -> Path:
        return Path(location)


@lru_cache
def _default_google_storage_client(location: str) -> Bucket:
    project, bucket = location.split(":")
    return GoogleStorageClient(project=project).bucket(bucket)


@dataclass(frozen=True)
class QueryJobsResponse:
    jobs: list[Job]
    next_page: Pagination

    @classmethod
    def from_message(cls, page: job_pb2.QueryJobsResponse) -> "QueryJobsResponse":
        return cls(
            jobs=[Job.from_message(job) for job in page.jobs],
            next_page=Pagination.from_message(page.next_page),
        )

    def to_message(self) -> job_pb2.QueryJobsResponse:
        return job_pb2.QueryJobsResponse(
            jobs=[job.to_message() for job in self.jobs],
            next_page=self.next_page.to_message(),
        )


@dataclass(frozen=True)
class QueryFilters:
    time_interval: TimeInterval | None = None
    id_interval: IDInterval | None = None
    automation_id: UUID | None = None

    @classmethod
    def from_message(cls, filters: job_pb2.QueryFilters) -> "QueryFilters":
        return cls(
            time_interval=TimeInterval.from_message(filters.time_interval),
            id_interval=IDInterval.from_message(filters.id_interval),
            automation_id=uuid_message_to_optional_uuid(filters.automation_id),
        )

    def to_message(self) -> job_pb2.QueryFilters:
        return job_pb2.QueryFilters(
            time_interval=self.time_interval.to_message() if self.time_interval else None,
            id_interval=self.id_interval.to_message() if self.id_interval else None,
            automation_id=uuid_to_uuid_message(self.automation_id) if self.automation_id else None,
        )
