from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from app.models import Summary, TaskCreate, TaskStatus, TaskUpdate
from app.store import TaskStore, get_store

START = datetime(2026, 11, 22, 9, 30, tzinfo=UTC)


def ticking_clock(step: timedelta = timedelta(seconds=1)) -> Callable[[], datetime]:
    """A clock that moves forward by `step` on every call, starting at START."""
    now = START - step

    def clock() -> datetime:
        nonlocal now
        now += step
        return now

    return clock


@pytest.fixture
def store() -> TaskStore:
    return TaskStore(clock=ticking_clock())


def add(store: TaskStore, title: str = "t", **fields) -> UUID:
    return store.add(TaskCreate(title=title, **fields)).id


def update(store: TaskStore, task_id: UUID, **changes):
    return store.update(task_id, TaskUpdate.model_validate(changes))


class TestAdd:
    def test_makes_id_and_created_at_and_starts_open(self, store):
        task = store.add(TaskCreate(title="Buy milk", notes="2 litres", due=date(2026, 11, 23)))
        assert isinstance(task.id, UUID)
        assert task.created_at == START
        assert task.title == "Buy milk"
        assert task.notes == "2 litres"
        assert task.due == date(2026, 11, 23)
        assert task.done is False
        assert task.done_at is None

    def test_ids_are_unique(self, store):
        assert add(store) != add(store)

    def test_added_task_can_be_got(self, store):
        task = store.add(TaskCreate(title="t"))
        assert store.get(task.id) == task


class TestList:
    def test_empty_store_lists_nothing(self, store):
        assert store.list() == []

    def test_newest_first(self, store):
        first, second, third = add(store, "a"), add(store, "b"), add(store, "c")
        assert [t.id for t in store.list()] == [third, second, first]

    def test_ties_are_broken_by_insertion_order_latest_first(self):
        store = TaskStore(clock=lambda: START)
        first, second = add(store, "a"), add(store, "b")
        assert [t.id for t in store.list()] == [second, first]

    def test_filters_by_status(self, store):
        open_id, done_id = add(store, "open"), add(store, "done")
        update(store, done_id, done=True)
        assert [t.id for t in store.list(TaskStatus.open)] == [open_id]
        assert [t.id for t in store.list(TaskStatus.done)] == [done_id]
        assert [t.id for t in store.list(TaskStatus.all)] == [done_id, open_id]


class TestUnknownId:
    def test_get_returns_none(self, store):
        assert store.get(uuid4()) is None

    def test_update_returns_none(self, store):
        assert update(store, uuid4(), title="x") is None

    def test_delete_returns_false(self, store):
        assert store.delete(uuid4()) is False


class TestUpdate:
    def test_changes_only_the_fields_sent(self, store):
        task_id = add(store, "old", notes="keep", due=date(2026, 11, 23))
        task = update(store, task_id, title=" new ")
        assert task.title == "new"
        assert task.notes == "keep"
        assert task.due == date(2026, 11, 23)
        assert store.get(task_id) == task

    def test_empty_update_changes_nothing(self, store):
        task_id = add(store)
        before = store.get(task_id)
        assert update(store, task_id) == before

    def test_due_null_clears_the_date_and_absent_keeps_it(self, store):
        task_id = add(store, due=date(2026, 11, 23))
        assert update(store, task_id, notes="x").due == date(2026, 11, 23)
        assert update(store, task_id, due=None).due is None

    def test_done_sets_done_at_and_undone_clears_it(self, store):
        task_id = add(store)  # created at START
        done = update(store, task_id, done=True)
        assert done.done is True
        assert done.done_at == START + timedelta(seconds=1)
        undone = update(store, task_id, done=False)
        assert undone.done is False
        assert undone.done_at is None

    def test_sending_the_current_done_leaves_done_at(self, store):
        task_id = add(store)
        done_at = update(store, task_id, done=True).done_at
        assert update(store, task_id, done=True).done_at == done_at
        assert update(store, add(store), done=False).done_at is None

    def test_id_and_created_at_never_change(self, store):
        task = store.add(TaskCreate(title="t"))
        changed = update(store, task.id, title="u", done=True)
        assert (changed.id, changed.created_at) == (task.id, task.created_at)


class TestDelete:
    def test_deletes_the_task(self, store):
        task_id = add(store)
        assert store.delete(task_id) is True
        assert store.get(task_id) is None
        assert store.delete(task_id) is False


class TestSummary:
    def test_empty(self, store):
        assert store.summary() == Summary(total=0, open=0, done=0)

    def test_counts_open_and_done(self, store):
        add(store)
        add(store)
        update(store, add(store), done=True)
        assert store.summary() == Summary(total=3, open=2, done=1)


class TestIsolation:
    def test_fresh_instances_share_nothing(self):
        one, two = TaskStore(), TaskStore()
        add(one)
        assert two.list() == []

    def test_default_clock_is_utc(self):
        task = TaskStore().add(TaskCreate(title="t"))
        assert task.created_at.utcoffset() == timedelta(0)

    def test_get_store_returns_one_shared_store(self):
        assert get_store() is get_store()
