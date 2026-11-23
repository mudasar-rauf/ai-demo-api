"""GET /tasks and POST /tasks, through the API, with tasks seeded through the store."""

import re
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from app.main import app
from app.models import NOTES_MAX_LENGTH, TITLE_MAX_LENGTH, TaskCreate, TaskUpdate
from app.store import TaskStore, get_store

START = datetime(2026, 11, 22, 9, 30, 15, 123456, tzinfo=UTC)
ISO_UTC = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z")


class Clock:
    """A controllable clock: returns `now` and then moves it forward by `step`."""

    def __init__(self, now: datetime = START, step: timedelta = timedelta(seconds=1)) -> None:
        self.now = now
        self.step = step

    def __call__(self) -> datetime:
        current = self.now
        self.now += self.step
        return current


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def store(clock: Clock) -> TaskStore:
    return TaskStore(clock=clock)


def add(store: TaskStore, title: str, **fields) -> str:
    return str(store.add(TaskCreate(title=title, **fields)).id)


def mark_done(store: TaskStore, task_id: str) -> None:
    store.update(UUID(task_id), TaskUpdate(done=True))


def titles(response) -> list[str]:
    return [task["title"] for task in response.json()]


class TestListOrder:
    """AC1."""

    def test_empty_store_lists_nothing(self, client):
        response = client.get("/tasks")
        assert response.status_code == 200
        assert response.json() == []

    def test_newest_first_by_created_at(self, client, store):
        for title in ("first", "second", "third"):
            add(store, title)
        response = client.get("/tasks")
        assert response.status_code == 200
        assert titles(response) == ["third", "second", "first"]

    def test_same_created_at_lists_latest_added_first(self, client, store, clock):
        clock.step = timedelta(0)
        for title in ("a", "b", "c"):
            add(store, title)
        assert titles(client.get("/tasks")) == ["c", "b", "a"]

    def test_mixed_times_and_ties(self, client, store, clock):
        clock.step = timedelta(0)
        add(store, "early-1")
        add(store, "early-2")
        clock.now += timedelta(minutes=1)
        add(store, "late-1")
        add(store, "late-2")
        assert titles(client.get("/tasks")) == ["late-2", "late-1", "early-2", "early-1"]

    def test_tasks_carry_every_field(self, client, store):
        task_id = add(store, "Buy milk", notes="2 litres", due="2026-11-23")
        assert client.get("/tasks").json() == [
            {
                "id": task_id,
                "title": "Buy milk",
                "notes": "2 litres",
                "due": "2026-11-23",
                "done": False,
                "created_at": "2026-11-22T09:30:15.123456Z",
                "done_at": None,
            }
        ]


class TestListFilter:
    """AC2."""

    @pytest.fixture
    def seeded(self, store):
        add(store, "open-1")
        done_id = add(store, "done-1")
        add(store, "open-2")
        mark_done(store, done_id)

    def test_open_gives_only_open_tasks(self, client, seeded):
        response = client.get("/tasks", params={"status": "open"})
        assert response.status_code == 200
        assert titles(response) == ["open-2", "open-1"]
        assert all(task["done"] is False for task in response.json())

    def test_done_gives_only_done_tasks(self, client, seeded):
        response = client.get("/tasks", params={"status": "done"})
        assert response.status_code == 200
        assert titles(response) == ["done-1"]
        assert response.json()[0]["done"] is True

    @pytest.mark.parametrize("params", [{}, {"status": "all"}])
    def test_all_or_no_status_gives_every_task(self, client, seeded, params):
        response = client.get("/tasks", params=params)
        assert response.status_code == 200
        assert titles(response) == ["open-2", "done-1", "open-1"]

    @pytest.mark.parametrize("status", ["later", "OPEN", "", "true"])
    def test_any_other_status_is_422(self, client, seeded, status):
        assert client.get("/tasks", params={"status": status}).status_code == 422


class TestCreate:
    """AC3."""

    def test_creates_a_task_with_defaults(self, client):
        response = client.post("/tasks", json={"title": "  Buy milk  "})
        assert response.status_code == 201
        task = response.json()
        assert task["title"] == "Buy milk"
        assert task["notes"] == ""
        assert task["due"] is None
        assert task["done"] is False
        assert task["done_at"] is None
        assert UUID(task["id"])
        assert task["created_at"] == "2026-11-22T09:30:15.123456Z"

    def test_created_at_has_six_digits_on_a_whole_second(self, client, clock):
        clock.now = datetime(2026, 11, 23, 8, 0, tzinfo=UTC)
        response = client.post("/tasks", json={"title": "t"})
        assert response.json()["created_at"] == "2026-11-23T08:00:00.000000Z"

    def test_created_at_is_now_with_the_real_clock(self, client):
        app.dependency_overrides[get_store] = lambda: TaskStore()  # its default clock
        before = datetime.now(UTC)
        created_at = client.post("/tasks", json={"title": "t"}).json()["created_at"]
        after = datetime.now(UTC)
        assert ISO_UTC.fullmatch(created_at)
        parsed = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=UTC)
        assert before <= parsed <= after

    def test_echoes_notes_and_due(self, client):
        response = client.post(
            "/tasks", json={"title": "Buy milk", "notes": "2 litres", "due": "2026-11-23"}
        )
        assert response.status_code == 201
        assert response.json()["notes"] == "2 litres"
        assert response.json()["due"] == "2026-11-23"

    def test_accepts_the_limits(self, client):
        response = client.post(
            "/tasks",
            json={"title": "t" * TITLE_MAX_LENGTH, "notes": "n" * NOTES_MAX_LENGTH, "due": None},
        )
        assert response.status_code == 201

    def test_each_task_gets_a_new_id(self, client):
        first = client.post("/tasks", json={"title": "a"}).json()["id"]
        second = client.post("/tasks", json={"title": "b"}).json()["id"]
        assert first != second

    def test_created_task_is_stored_and_listed(self, client, store):
        task = client.post("/tasks", json={"title": "Buy milk"}).json()
        assert client.get("/tasks").json() == [task]
        assert str(store.get(UUID(task["id"])).id) == task["id"]


class TestCreateValidation:
    """AC4."""

    @pytest.mark.parametrize(
        "body",
        [
            pytest.param({}, id="missing-title"),
            pytest.param({"title": None}, id="null-title"),
            pytest.param({"title": "   "}, id="blank-title"),
            pytest.param({"title": "t" * (TITLE_MAX_LENGTH + 1)}, id="title-201"),
            pytest.param({"title": "t", "notes": "n" * (NOTES_MAX_LENGTH + 1)}, id="notes-2001"),
            pytest.param({"title": "t", "due": "23/11/2026"}, id="due-dmy"),
            pytest.param({"title": "t", "due": "2026-13-01"}, id="due-bad-month"),
            pytest.param({"title": "t", "due": "tomorrow"}, id="due-word"),
            pytest.param({"title": "t", "due": 1763856000}, id="due-number"),
            pytest.param({"title": "t", "due": "1763856000"}, id="due-numeric-string"),
            pytest.param({"title": "t", "id": "00000000-0000-0000-0000-000000000000"}, id="id"),
            pytest.param(
                {"title": "t", "created_at": "2026-11-22T09:30:00.000000Z"}, id="created_at"
            ),
            pytest.param({"title": "t", "done_at": None}, id="done_at"),
            pytest.param({"title": "t", "done": False}, id="done"),
            pytest.param({"title": "t", "priority": 1}, id="priority"),
        ],
    )
    def test_invalid_body_is_422_and_stores_nothing(self, client, store, body):
        assert client.post("/tasks", json=body).status_code == 422
        assert store.list() == []
