"""GET, PATCH and DELETE /tasks/{task_id}, through the HTTP boundary.

Tasks are seeded through the store, never through POST /tasks.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.models import TaskCreate, TaskUpdate
from app.store import TaskStore

NOT_FOUND = {"detail": "Task not found"}
START = datetime(2026, 11, 23, 9, 30, 0, 123456, tzinfo=UTC)


class SteppingClock:
    """Starts at START and moves on a minute each time it is read."""

    def __init__(self) -> None:
        self.now = START - timedelta(minutes=1)

    def __call__(self) -> datetime:
        self.now += timedelta(minutes=1)
        return self.now


def wire(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


@pytest.fixture
def clock() -> SteppingClock:
    return SteppingClock()


@pytest.fixture
def store(clock: SteppingClock) -> TaskStore:
    """Overrides conftest's store with one on a known clock, so done_at can be asserted."""
    return TaskStore(clock=clock)


@pytest.fixture
def task(store: TaskStore):
    return store.add(TaskCreate(title="Buy milk", notes="Semi-skimmed", due="2026-11-30"))


def as_json(task) -> dict:
    return task.model_dump(mode="json")


# AC1: GET /tasks/{id}


def test_get_answers_the_task(client, task):
    response = client.get(f"/tasks/{task.id}")

    assert response.status_code == 200
    assert response.json() == {
        "id": str(task.id),
        "title": "Buy milk",
        "notes": "Semi-skimmed",
        "due": "2026-11-30",
        "done": False,
        "created_at": wire(START),
        "done_at": None,
    }


def test_get_of_a_done_task_shows_done_at(client, store, task):
    store.update(task.id, TaskUpdate(done=True))

    body = client.get(f"/tasks/{task.id}").json()

    assert body["done"] is True
    assert body["done_at"] == wire(START + timedelta(minutes=1))


def test_get_of_an_unknown_id_is_404(client, task):
    response = client.get(f"/tasks/{uuid4()}")

    assert response.status_code == 404
    assert response.json() == NOT_FOUND


def test_get_of_a_non_uuid_id_is_422(client):
    assert client.get("/tasks/not-a-uuid").status_code == 422


# AC2: PATCH /tasks/{id}


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        ({"title": "  Buy oat milk  "}, {"title": "Buy oat milk"}),
        ({"notes": ""}, {"notes": ""}),
        ({"notes": "Two litres"}, {"notes": "Two litres"}),
        ({"due": "2026-12-01"}, {"due": "2026-12-01"}),
        ({"due": None}, {"due": None}),
    ],
)
def test_patch_changes_only_the_fields_sent(client, store, task, change, expected):
    before = as_json(task)

    response = client.patch(f"/tasks/{task.id}", json=change)

    assert response.status_code == 200
    assert response.json() == {**before, **expected}
    assert as_json(store.get(task.id)) == {**before, **expected}


def test_patch_changes_several_fields_at_once(client, store, task):
    response = client.patch(
        f"/tasks/{task.id}", json={"title": "Buy bread", "notes": "", "due": None}
    )

    assert response.status_code == 200
    body = response.json()
    assert (body["title"], body["notes"], body["due"]) == ("Buy bread", "", None)
    assert body == as_json(store.get(task.id))


def test_patch_with_an_empty_body_changes_nothing(client, store, task):
    response = client.patch(f"/tasks/{task.id}", json={})

    assert response.status_code == 200
    assert response.json() == as_json(task)
    assert store.get(task.id) == task


@pytest.mark.parametrize("field", ["title", "notes", "done"])
def test_patch_refuses_null_for_non_nullable_fields(client, store, task, field):
    assert client.patch(f"/tasks/{task.id}", json={field: None}).status_code == 422
    assert store.get(task.id) == task


@pytest.mark.parametrize(
    "change",
    [
        {"title": ""},
        {"title": "   "},
        {"title": "x" * 201},
        {"notes": "x" * 2001},
        {"due": "23-11-2026"},
        {"due": "2026-02-30"},
        {"due": 1763856000},
        {"due": "1763856000"},
        {"done": "maybe"},
    ],
)
def test_patch_refuses_a_field_breaking_its_rule(client, store, task, change):
    assert client.patch(f"/tasks/{task.id}", json=change).status_code == 422
    assert store.get(task.id) == task


@pytest.mark.parametrize(
    "change",
    [
        {"id": str(uuid4())},
        {"created_at": "2026-01-01T00:00:00.000000Z"},
        {"done_at": "2026-01-01T00:00:00.000000Z"},
        {"foo": "bar"},
        {"title": "Allowed", "foo": "bar"},
    ],
)
def test_patch_refuses_any_other_field(client, store, task, change):
    assert client.patch(f"/tasks/{task.id}", json=change).status_code == 422
    assert store.get(task.id) == task


def test_patch_of_an_unknown_id_is_404(client, task):
    response = client.patch(f"/tasks/{uuid4()}", json={"title": "Anything"})

    assert response.status_code == 404
    assert response.json() == NOT_FOUND


def test_patch_of_a_non_uuid_id_is_422(client):
    assert client.patch("/tasks/not-a-uuid", json={}).status_code == 422


# AC3: done and done_at


def test_marking_done_sets_done_at_to_now(client, task):
    body = client.patch(f"/tasks/{task.id}", json={"done": True}).json()

    assert body["done"] is True
    assert body["done_at"] == wire(START + timedelta(minutes=1))


def test_marking_not_done_clears_done_at(client, store, task):
    store.update(task.id, TaskUpdate(done=True))

    body = client.patch(f"/tasks/{task.id}", json={"done": False}).json()

    assert body["done"] is False
    assert body["done_at"] is None


def test_sending_done_true_again_keeps_done_at(client, clock, task):
    first = client.patch(f"/tasks/{task.id}", json={"done": True}).json()
    clock()  # time moves on before the second call

    second = client.patch(f"/tasks/{task.id}", json={"done": True}).json()

    assert second["done"] is True
    assert second["done_at"] == first["done_at"] == wire(START + timedelta(minutes=1))


def test_sending_done_false_again_keeps_done_at_null(client, task):
    body = client.patch(f"/tasks/{task.id}", json={"done": False}).json()

    assert body["done"] is False
    assert body["done_at"] is None


def test_changing_other_fields_of_a_done_task_keeps_done_at(client, store, task):
    done = store.update(task.id, TaskUpdate(done=True))

    body = client.patch(f"/tasks/{task.id}", json={"title": "Buy cheese"}).json()

    assert body["done_at"] == wire(done.done_at)


# AC4: DELETE /tasks/{id}


def test_delete_answers_204_and_the_task_is_gone(client, store, task):
    response = client.delete(f"/tasks/{task.id}")

    assert response.status_code == 204
    assert response.content == b""
    assert store.get(task.id) is None
    get = client.get(f"/tasks/{task.id}")
    assert get.status_code == 404
    assert get.json() == NOT_FOUND


def test_delete_leaves_other_tasks(client, store, task):
    other = store.add(TaskCreate(title="Walk the dog"))

    client.delete(f"/tasks/{task.id}")

    assert client.get(f"/tasks/{other.id}").json() == as_json(other)


def test_delete_of_an_unknown_id_is_404(client, store, task):
    response = client.delete(f"/tasks/{uuid4()}")

    assert response.status_code == 404
    assert response.json() == NOT_FOUND
    assert store.get(task.id) == task


def test_deleting_twice_is_404_the_second_time(client, task):
    assert client.delete(f"/tasks/{task.id}").status_code == 204
    assert client.delete(f"/tasks/{task.id}").status_code == 404


def test_delete_of_a_non_uuid_id_is_422(client):
    assert client.delete("/tasks/not-a-uuid").status_code == 422
