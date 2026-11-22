"""The in-memory task store. Routes reach it only through Depends(get_store)."""

from collections.abc import Callable
from datetime import UTC, datetime
from threading import Lock
from uuid import UUID, uuid4

from app.models import Summary, Task, TaskCreate, TaskStatus, TaskUpdate

Clock = Callable[[], datetime]


def _utc_now() -> datetime:
    return datetime.now(UTC)


class TaskStore:
    """Tasks kept in a dict, in insertion order.

    FastAPI runs sync handlers in a threadpool, so every method holds one lock: a
    read-modify-write in update() cannot interleave with another call.
    """

    def __init__(self, clock: Clock = _utc_now) -> None:
        self._clock = clock
        self._tasks: dict[UUID, Task] = {}
        self._lock = Lock()

    def list(self, status: TaskStatus = TaskStatus.all) -> list[Task]:
        """Newest first: created_at descending, ties broken by insertion order, latest first."""
        with self._lock:
            tasks = [t for t in reversed(self._tasks.values()) if _matches(t, status)]
        return sorted(tasks, key=lambda t: t.created_at, reverse=True)

    def add(self, data: TaskCreate) -> Task:
        with self._lock:
            task = Task(
                id=uuid4(),
                title=data.title,
                notes=data.notes,
                due=data.due,
                done=False,
                created_at=self._clock(),
                done_at=None,
            )
            self._tasks[task.id] = task
        return task

    def get(self, task_id: UUID) -> Task | None:
        with self._lock:
            return self._tasks.get(task_id)

    def update(self, task_id: UUID, changes: TaskUpdate) -> Task | None:
        """Applies the fields sent; sets done_at when done becomes true, clears it when false."""
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return None
            fields = changes.model_dump(exclude_unset=True)
            if "done" in fields and fields["done"] != task.done:
                fields["done_at"] = self._clock() if fields["done"] else None
            updated = task.model_copy(update=fields)
            self._tasks[task_id] = updated
        return updated

    def delete(self, task_id: UUID) -> bool:
        with self._lock:
            return self._tasks.pop(task_id, None) is not None

    def summary(self) -> Summary:
        with self._lock:
            done = sum(1 for t in self._tasks.values() if t.done)
            total = len(self._tasks)
        return Summary(total=total, open=total - done, done=done)


def _matches(task: Task, status: TaskStatus) -> bool:
    if status is TaskStatus.open:
        return not task.done
    if status is TaskStatus.done:
        return task.done
    return True


_store = TaskStore()


def get_store() -> TaskStore:
    """The app's one store. Tests replace it through app.dependency_overrides."""
    return _store
