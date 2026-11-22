from datetime import UTC, date, datetime, timedelta, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.models import Task, TaskCreate, TaskUpdate


def make_task(**overrides) -> Task:
    fields = {
        "id": uuid4(),
        "title": "Buy milk",
        "notes": "",
        "due": None,
        "done": False,
        "created_at": datetime(2026, 11, 22, 9, 30, tzinfo=UTC),
        "done_at": None,
    }
    return Task(**(fields | overrides))


class TestTaskCreate:
    def test_title_is_trimmed(self):
        assert TaskCreate(title="  Buy milk  ").title == "Buy milk"

    def test_notes_default_to_empty_and_due_to_none(self):
        task = TaskCreate(title="Buy milk")
        assert task.notes == ""
        assert task.due is None

    def test_notes_are_not_trimmed(self):
        assert TaskCreate(title="t", notes="  x  ").notes == "  x  "

    @pytest.mark.parametrize("title", ["", "   ", "x" * 201])
    def test_bad_titles_are_rejected(self, title):
        with pytest.raises(ValidationError):
            TaskCreate(title=title)

    def test_title_of_200_characters_is_accepted(self):
        assert len(TaskCreate(title="x" * 200).title) == 200

    def test_title_is_required(self):
        with pytest.raises(ValidationError):
            TaskCreate.model_validate({})

    def test_notes_of_2000_characters_are_accepted_and_2001_rejected(self):
        assert len(TaskCreate(title="t", notes="n" * 2000).notes) == 2000
        with pytest.raises(ValidationError):
            TaskCreate(title="t", notes="n" * 2001)

    def test_due_parses_a_date(self):
        assert TaskCreate.model_validate({"title": "t", "due": "2026-11-23"}).due == date(
            2026, 11, 23
        )

    def test_bad_due_is_rejected(self):
        with pytest.raises(ValidationError):
            TaskCreate.model_validate({"title": "t", "due": "23/11/2026"})

    @pytest.mark.parametrize("field", ["id", "done", "created_at", "done_at", "colour"])
    def test_other_fields_are_rejected(self, field):
        with pytest.raises(ValidationError):
            TaskCreate.model_validate({"title": "t", field: "x"})


class TestTaskUpdate:
    @pytest.mark.parametrize("field", ["title", "notes", "done"])
    def test_null_is_rejected_for_non_nullable_fields(self, field):
        with pytest.raises(ValidationError):
            TaskUpdate.model_validate({field: None})

    def test_null_due_is_accepted_and_marked_as_sent(self):
        update = TaskUpdate.model_validate({"due": None})
        assert update.due is None
        assert update.model_fields_set == {"due"}

    def test_empty_body_sets_nothing(self):
        update = TaskUpdate.model_validate({})
        assert update.model_fields_set == set()
        assert update.model_dump(exclude_unset=True) == {}

    def test_title_is_trimmed_and_validated(self):
        assert TaskUpdate.model_validate({"title": " t "}).title == "t"
        with pytest.raises(ValidationError):
            TaskUpdate.model_validate({"title": "  "})

    def test_notes_over_2000_characters_are_rejected(self):
        with pytest.raises(ValidationError):
            TaskUpdate.model_validate({"notes": "n" * 2001})

    @pytest.mark.parametrize("field", ["id", "created_at", "done_at", "colour"])
    def test_read_only_and_unknown_fields_are_rejected(self, field):
        with pytest.raises(ValidationError):
            TaskUpdate.model_validate({field: "x"})

    def test_schema_shows_only_due_as_nullable(self):
        properties = TaskUpdate.model_json_schema()["properties"]
        assert properties["title"]["type"] == "string"
        assert properties["notes"]["type"] == "string"
        assert properties["done"]["type"] == "boolean"
        assert {"type": "null"} in properties["due"]["anyOf"]


class TestTaskSerialisation:
    def test_whole_second_is_sent_with_six_fractional_digits(self):
        body = make_task().model_dump(mode="json")
        assert body["created_at"] == "2026-11-22T09:30:00.000000Z"

    def test_microseconds_are_kept(self):
        created = datetime(2026, 11, 22, 9, 30, 0, 123456, tzinfo=UTC)
        body = make_task(created_at=created, done_at=created).model_dump(mode="json")
        assert body["created_at"] == "2026-11-22T09:30:00.123456Z"
        assert body["done_at"] == "2026-11-22T09:30:00.123456Z"

    def test_other_offsets_are_converted_to_utc(self):
        created = datetime(2026, 11, 22, 11, 30, tzinfo=timezone(timedelta(hours=2)))
        body = make_task(created_at=created).model_dump(mode="json")
        assert body["created_at"] == "2026-11-22T09:30:00.000000Z"

    def test_naive_datetime_is_rejected(self):
        with pytest.raises(ValidationError):
            make_task(created_at=datetime(2026, 11, 22, 9, 30))

    def test_null_done_at_and_due_are_sent_as_null(self):
        body = make_task().model_dump(mode="json")
        assert body["done_at"] is None
        assert body["due"] is None

    def test_body_has_exactly_the_contract_fields(self):
        assert set(make_task().model_dump(mode="json")) == {
            "id",
            "title",
            "notes",
            "due",
            "done",
            "created_at",
            "done_at",
        }

    def test_schema_keeps_the_date_time_format(self):
        properties = Task.model_json_schema(mode="serialization")["properties"]
        assert properties["created_at"]["format"] == "date-time"
