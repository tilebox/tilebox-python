from tilebox.workflows.cache import JobCache
from tilebox.workflows.data import TaskIdentifier
from tilebox.workflows.task import RunnerContext, Task, TaskMeta


class Runner:
    def __init__(
        self,
        *,
        tasks: list[type[Task]] | None = None,
        cache: JobCache | None = None,
        context: type[RunnerContext] | None = None,
    ) -> None:
        self.cache = cache
        self.context = context
        self._tasks_by_identifier: dict[TaskIdentifier, type[Task]] = {}

        for task in tasks or []:
            self.register(task)

    def register(self, task: type[Task]) -> None:
        """Register a task that can be executed by this runner."""
        meta = TaskMeta.for_task(task)  # ensures that this is a valid task
        if not meta.executable:
            task_repr = task.__name__
            if meta.identifier.name != task.__name__:
                task_repr += f" ({meta.identifier.name})"
            raise ValueError(
                f"Task {task_repr} is not executable. It must have an execute method in order to "
                f"register it with a task runner."
            )
        if meta.identifier in self._tasks_by_identifier:
            raise ValueError(
                f"Duplicate task identifier: A task '{meta.identifier.name}' with version '{meta.identifier.version}' "
                f"is already registered."
            )
        self._tasks_by_identifier[meta.identifier] = task

    @property
    def task_identifiers(self) -> list[TaskIdentifier]:
        return list(self._tasks_by_identifier)

    @property
    def tasks_by_identifier(self) -> dict[TaskIdentifier, type[Task]]:
        return self._tasks_by_identifier
