# Technical Plan: #9 The due date accepts only YYYY-MM-DD

**Ticket:** #9   **Spec:** [docs/specs/9-due-date-accepts-only.md](../specs/9-due-date-accepts-only.md)   **Status:** Draft

## 1. Summary

`TaskCreate.due` and `TaskUpdate.due` are typed `date | None`, and Pydantic's lax date parsing also accepts Unix timestamps (ints, floats, numeric strings) and other shapes, which the contract does not allow. We add one annotated type, `DueDate`, in `app/models.py`: a `BeforeValidator` that lets through only a `str` matching `^\d{4}-\d{2}-\d{2}$` (or an actual `date` that is not a `datetime`), then lets Pydantic's normal date parsing refuse impossible dates. Both input models use it; `Task`, the routes and the store do not change. One small task (S).

## 2. Requirements

### Acceptance criteria

| ID | Criterion | Source |
|---|---|---|
| AC1 | `TaskCreate` and `TaskUpdate` refuse a number, a numeric string such as `"1763856000"`, or any string not shaped `YYYY-MM-DD` | ticket |
| AC2 | A real `YYYY-MM-DD` is accepted, `"2026-02-30"` is refused, `null` is accepted; in `TaskUpdate`, `due: null` still clears the date | ticket |
| AC3 | `tests/test_models.py` covers AC1 and AC2 for both models; Ruff and pytest pass in CI | ticket |
| AC4 | OpenAPI still shows `due` as string format `date` or null; `Task` and the store are unchanged | derived |

### Out of scope

`docs/contracts/api.md` (it already says `YYYY-MM-DD`), routes, store and their tests. `Task.due` (a response model, built by the store from already-validated `date` values).

### Assumptions

- "Shaped `YYYY-MM-DD`" means exactly four digits, hyphen, two digits, hyphen, two digits, nothing before or after. So `"2026-2-3"`, `"20261123"`, `" 2026-11-23"`, `"2026-11-23T00:00:00"` and `"2026-11-23Z"` are all refused. Only ASCII digits: the regex uses `[0-9]`, not `\d`, which also matches other Unicode digits.
- A Python `date` instance is still accepted (tests and any internal caller build models with `date(...)`); a `datetime` instance is refused, since `datetime` subclasses `date` and Pydantic would otherwise truncate it.
- `bool` is a number for this purpose and is refused (it falls in the "not a str" branch).

## 3. Current state

- `app/models.py`: `TaskCreate.due: date | None = None` and `TaskUpdate.due: date | None = None`. `TaskUpdate` is read with `model_dump(exclude_unset=True)`, so `due: null` is "sent and cleared", absent is "unchanged" (`tests/test_models.py::TestTaskUpdate::test_null_due_is_accepted_and_marked_as_sent`).
- Pydantic v2 lax mode (pinned 2.14.4) parses `date` from ints/floats as Unix seconds, from numeric strings likewise, and from datetime strings whose time part is zero. That is the bug.
- FastAPI validates the parsed JSON body in Python mode, so a `BeforeValidator` sees the JSON value (`int`, `str`, `None`, ...).
- Existing tests: `test_due_parses_a_date`, `test_bad_due_is_rejected` (TaskCreate only).

## 4. Proposed design

In `app/models.py`, next to `TitleStr` / `NotesStr`:

```python
_DUE_SHAPE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")

def _due_shape(value: object) -> object:
    """Only a YYYY-MM-DD string (or a date that is not a datetime) goes on to date parsing."""
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, str) and _DUE_SHAPE.fullmatch(value):
        return value
    raise ValueError("due must be a date in YYYY-MM-DD form")

DueDate = Annotated[date, BeforeValidator(_due_shape)]
```

Fields become `due: DueDate | None = None` in both `TaskCreate` and `TaskUpdate`. With `DueDate | None`, Pydantic's union handles `None` before the `date` branch's validator runs, so `null` stays valid and `TaskUpdate`'s `model_fields_set` behaviour is unchanged. After the shape check, Pydantic's own date parsing refuses `"2026-02-30"` and `"2026-13-01"`. A `ValueError` in a validator becomes a `ValidationError`, which FastAPI answers with 422, as today.

| File | Change |
|---|---|
| `app/models.py` | add `DueDate`; use it for `TaskCreate.due` and `TaskUpdate.due`; import `re`, `BeforeValidator` |
| `tests/test_models.py` | new tests below |

Schema: `BeforeValidator` does not change the JSON schema, so `due` still appears as `{"type": "string", "format": "date"}` or null (AC4).

## 5. Key decisions

| Decision | Choice | Rationale | Alternatives rejected |
|---|---|---|---|
| How to restrict input | `BeforeValidator` with a strict regex, then normal date parsing | Smallest change; keeps calendar validation and schema | `Field(strict=True)`: in Python mode (what FastAPI uses) strict `date` refuses every string, so it would refuse valid input. `StringConstraints(pattern=...)` on a `str` field: changes the field's type away from `date`, touching the store and routes |
| Where | one shared `DueDate` type | Both models need the identical rule | duplicate `field_validator`s per model |
| Feature flag | none | Ticket says "No feature flag: merging it is the fix". This is a correction to match the existing contract, not a new feature; a flag would keep the bug reachable | env var guarding the validator — flagged for the plan gate in case the factory's default rule should apply |

## 6. Implementation tasks

### T1. Restrict `due` to `YYYY-MM-DD` (S)
- Goal: AC1, AC2, AC4.
- Changes: `app/models.py`, `tests/test_models.py`.
- Details: as section 4. Write the tests first; they fail today for the numeric cases.
- Done when: all tests below pass; `ruff check`, `ruff format --check` and `pytest` pass.
- Tests: in `tests/test_models.py`, for **both** `TaskCreate` (with `title`) and `TaskUpdate` (alone), via `model_validate` with dict input as FastAPI does:
  - refused (`ValidationError`): `1763856000`, `1763856000.0`, `True`, `"1763856000"`, `"20261123"`, `"2026-2-3"`, `" 2026-11-23"`, `"2026-11-23T00:00:00"`, `"23/11/2026"`, `"2026-02-30"`, `"2026-13-01"`, and a `datetime(2026, 11, 23)` instance.
  - accepted: `"2026-11-23"` → `date(2026, 11, 23)`; `"2028-02-29"` (leap day); `None`; a `date(2026, 11, 23)` instance.
  - `TaskUpdate.model_validate({"due": None})` keeps `due` in `model_fields_set` (existing test stays).
  - Schema: `TaskCreate.model_json_schema()["properties"]["due"]["anyOf"]` contains `{"type": "string", "format": "date"}` and `{"type": "null"}`.
  - Use `pytest.mark.parametrize` across the two models to keep it short.
- Depends on: none.

## 7. Test strategy

| AC | Task | Type | Verifies |
|---|---|---|---|
| AC1 | T1 | unit (models) | numbers, numeric strings and non-`YYYY-MM-DD` strings refused, both models |
| AC2 | T1 | unit (models) | real date and leap day accepted, impossible dates refused, null accepted and marked set in `TaskUpdate` |
| AC3 | T1 | CI | Ruff and pytest green on the PR |
| AC4 | T1 | unit (schema) | OpenAPI shape of `due` unchanged |

Regression risk: route tests that post `due` (none today use a non-`YYYY-MM-DD` form); the existing `test_due_parses_a_date` and `test_bad_due_is_rejected` must still pass.

## 8. Rollout and rollback

Plain code deploy, no migration and no feature flag (the ticket rules one out; see decision above). Behaviour change for clients: values that were silently mis-read now get 422, which is what the contract already says. Rollback: revert the PR.

## 9. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| A client relies on sending timestamps | Low | It gets 422 | Contract never allowed it; behaviour now matches the contract |
| Union order makes `None` hit the validator | Low | `null` refused | Explicit tests for `null` in both models |

## 11. Open questions

| # | Question | Who | Blocks | Assumption |
|---|---|---|---|---|
| 1 | The factory's default is a flag for every feature; the ticket says none. OK to ship without? | plan gate reviewer | no | No flag, per the ticket |

## 12. Follow-ups

None.
