"""The Pydantic models of the contract in docs/contracts/api.md, field for field."""

import re
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    PlainSerializer,
    StringConstraints,
    WithJsonSchema,
)

TITLE_MAX_LENGTH = 200
NOTES_MAX_LENGTH = 2000

TitleStr = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=TITLE_MAX_LENGTH)
]
NotesStr = Annotated[str, StringConstraints(max_length=NOTES_MAX_LENGTH)]

# [0-9], not \d: \d also matches non-ASCII digits.
_DUE_SHAPE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")


def _due_shape(value: object) -> object:
    """Only a YYYY-MM-DD string (or a date that is not a datetime) goes on to date parsing.

    Pydantic's lax date parsing would otherwise read numbers and numeric strings as Unix times,
    and truncate datetimes, which the contract does not allow. Impossible dates such as
    2026-02-30 pass this check and are refused by the date parsing after it.
    """
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, str) and _DUE_SHAPE.fullmatch(value):
        return value
    raise ValueError("due must be a date in YYYY-MM-DD form")


DueDate = Annotated[date, BeforeValidator(_due_shape)]


def _utc_iso(value: datetime) -> str:
    """Always six fractional digits and a Z, so clients see one shape (the contract's rule)."""
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


# AwareDatetime refuses naive values, which astimezone() would read as the host's local time.
# WithJsonSchema keeps "format: date-time" in OpenAPI, which PlainSerializer would drop.
UtcDateTime = Annotated[
    AwareDatetime,
    PlainSerializer(_utc_iso, return_type=str, when_used="json"),
    WithJsonSchema({"type": "string", "format": "date-time"}, mode="serialization"),
]


class TaskStatus(StrEnum):
    all = "all"
    open = "open"
    done = "done"


class TaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: TitleStr
    notes: NotesStr = ""
    due: DueDate | None = None


class TaskUpdate(BaseModel):
    """Only the fields sent change; read them with model_dump(exclude_unset=True).

    title, notes and done are non-nullable with an unset default: absent is fine, an explicit
    null is a 422. Pydantic does not validate defaults, so the None default is never checked.
    due is the only nullable field: null clears the date.
    """

    model_config = ConfigDict(extra="forbid")

    title: TitleStr = Field(default=None)
    notes: NotesStr = Field(default=None)
    due: DueDate | None = None
    done: bool = Field(default=None)


class Task(BaseModel):
    id: UUID
    title: str
    notes: str
    due: date | None
    done: bool
    created_at: UtcDateTime
    done_at: UtcDateTime | None


class Summary(BaseModel):
    total: int
    open: int
    done: int


class Health(BaseModel):
    status: Literal["ok"]
