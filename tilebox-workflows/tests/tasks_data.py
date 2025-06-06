"""
Hypothesis strategies for generating random test data for tests.
"""

import json
import string

from hypothesis.strategies import (
    DrawFn,
    booleans,
    composite,
    dictionaries,
    floats,
    integers,
    lists,
    none,
    one_of,
    recursive,
    sampled_from,
    text,
    uuids,
)

from tilebox.workflows.data import (
    Cluster,
    ComputedTask,
    CronTrigger,
    Job,
    RecurrentTaskPrototype,
    StorageEventTrigger,
    StorageLocation,
    StorageType,
    Task,
    TaskIdentifier,
    TaskLease,
    TaskState,
    TaskSubmission,
)


@composite
def alphanumerical_text(draw: DrawFn, min_size: int = 1, max_size: int = 100) -> str:
    # the text() strategy gets a bit crazy with utf codepoints, so lets restrict it a bit
    return draw(text(alphabet=string.ascii_letters + string.digits + "-_", min_size=min_size, max_size=max_size))


@composite
def clusters(draw: DrawFn) -> Cluster:
    """A hypothesis strategy for generating random clusters"""
    slug = draw(alphanumerical_text(min_size=4, max_size=20))
    return Cluster(slug, draw(alphanumerical_text()))


@composite
def tasks(draw: DrawFn) -> Task:
    """A hypothesis strategy for generating random tasks"""
    task_id = draw(uuids(version=4))
    identifier = draw(task_identifiers())
    state = draw(sampled_from(TaskState))
    task_input = draw(task_inputs())
    display = draw(alphanumerical_text())
    job = draw(jobs())
    parent_id = draw(one_of(uuids(version=4), none()))
    depends_on = draw(lists(uuids(), min_size=0, max_size=10))
    lease = draw(task_leases())
    retry_count = draw(integers(min_value=0, max_value=100))

    return Task(task_id, identifier, state, task_input, display, job, parent_id, depends_on, lease, retry_count)


@composite
def task_identifiers(draw: DrawFn) -> TaskIdentifier:
    """A hypothesis strategy for generating random task_identifiers"""
    task_name = draw(alphanumerical_text())
    major_version = draw(integers(min_value=0, max_value=100))
    minor_version = draw(integers(min_value=0, max_value=100))
    return TaskIdentifier(task_name, f"v{major_version}.{minor_version}")


@composite
def task_inputs(draw: DrawFn) -> bytes:
    """A hypothesis strategy for generating random task_inputs"""
    random_input = draw(
        recursive(
            one_of(none(), booleans(), floats(), text(string.printable)),
            lambda children: dictionaries(text(string.printable), children),
            max_leaves=5,
        )
    )
    return json.dumps(random_input).encode()


@composite
def jobs(draw: DrawFn) -> Job:
    """A hypothesis strategy for generating random jobs"""
    job_id = draw(uuids(version=4))
    name = draw(alphanumerical_text())
    trace_parent = draw(alphanumerical_text())
    completed = draw(booleans())

    return Job(job_id, name, trace_parent, completed)


@composite
def task_submissions(draw: DrawFn) -> TaskSubmission:
    """A hypothesis strategy for generating random sub_tasks"""
    cluster_slug = str(draw(uuids(version=4)))
    identifier = draw(task_identifiers())
    task_input = draw(task_inputs())
    dependencies: list[int] = []
    display = draw(alphanumerical_text())
    max_retries = draw(integers(min_value=0, max_value=100))

    return TaskSubmission(cluster_slug, identifier, task_input, dependencies, display, max_retries)


@composite
def computed_tasks(draw: DrawFn) -> ComputedTask:
    """A hypothesis strategy for generating random computed_tasks"""
    task_id = draw(uuids(version=4))
    display = draw(alphanumerical_text())
    subtasks: list[TaskSubmission] = draw(lists(task_submissions(), min_size=1, max_size=10))

    return ComputedTask(task_id, display, subtasks)


@composite
def task_leases(draw: DrawFn) -> TaskLease:
    """A hypothesis strategy for generating random task_leases"""
    lease = draw(integers(min_value=0, max_value=60 * 60))
    recommended_wait_until_next_extension = draw(integers(min_value=0, max_value=60 * 60))

    return TaskLease(lease, recommended_wait_until_next_extension)


@composite
def storage_locations(draw: DrawFn) -> StorageLocation:
    """A hypothesis strategy for generating random storage locations"""
    storage_location_id = draw(uuids(version=4))
    location = draw(alphanumerical_text(min_size=4, max_size=30))
    storage_type = draw(sampled_from(StorageType))

    return StorageLocation(storage_location_id, location, storage_type)


@composite
def cron_triggers(draw: DrawFn) -> CronTrigger:
    """A hypothesis strategy for generating random cron_triggers"""
    trigger_id = draw(uuids(version=4))
    minute = draw(integers(min_value=0, max_value=59))
    hour = draw(integers(min_value=0, max_value=23))
    cron_expression = f"{minute} {hour} * * *"
    return CronTrigger(trigger_id, cron_expression)


@composite
def storage_event_triggers(draw: DrawFn) -> StorageEventTrigger:
    """A hypothesis strategy for generating random storage_event_triggers"""
    trigger_id = draw(uuids(version=4))
    storage_location = draw(storage_locations())
    glob_pattern = draw(alphanumerical_text())
    return StorageEventTrigger(trigger_id, storage_location, glob_pattern)


@composite
def recurrent_tasks(draw: DrawFn) -> RecurrentTaskPrototype:
    """A hypothesis strategy for generating random recurrent tasks"""
    recurrent_task_id = draw(uuids(version=4))
    name = draw(alphanumerical_text())
    prototype = draw(task_submissions())

    storage_event = []
    cron = []

    is_cron = draw(booleans())
    if is_cron:
        cron = draw(lists(cron_triggers(), min_size=1, max_size=10))
    else:
        storage_event = draw(lists(storage_event_triggers(), min_size=1, max_size=10))

    return RecurrentTaskPrototype(recurrent_task_id, name, prototype, storage_event, cron)
