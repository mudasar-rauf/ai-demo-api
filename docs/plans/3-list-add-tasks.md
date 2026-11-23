# Technical Plan: #3 List and add tasks

**Ticket:** #3   **Spec:** [docs/specs/3-list-add-tasks.md](../specs/3-list-add-tasks.md)   **Status:** Draft

## 1. Summary

`GET /tasks` and `POST /tasks` are wired in `app/routes/tasks.py` but answer 501. The store (`app/store.py`) already does the work: `TaskStore.list(status)` filters and sorts newest first, and `TaskStore.add(data)` makes the id, `created_at`, `done=False` and `done_at=None`. The models (`app/models.py`) already enforce every 422 of AC2 and AC4. So the change is to make both handlers delegate to the store, behind an environment-variable flag that is off by default, and to replace the 501 tests with behaviour tests. One task, size S.

## 2. Requirements

### Acceptance criteria

| ID | Criterion (short) | Source |
|---|---|---|
| AC1 | `GET /tasks` → 200, newest first; same `created_at` → latest created first | ticket |
| AC2 | `status=open` / `done` filter; `all` or none → every task; other → 422 | ticket |
| AC3 | `POST /tasks` → 201 with trimmed title, defaults, `done=false`, `done_at=null`, new UUID, `created_at` now as `…​.ffffffZ` | ticket |
| AC4 | `POST /tasks` → 422 for missing/blank/over-200 title, over-2,000 notes, bad `due`, any extra field incl. `id`, `created_at`, `done_at` | ticket |
| AC5 | `tests/test_tasks.py` covers AC1–AC4 instead of the 501 checks, seeding through the store; Ruff and pytest pass in CI | ticket |
| D1 | Behind `TASKS_LIST_CREATE_ENABLED`, off by default; off → 501 as today | derived |

### Out of scope

`/tasks/{id}` endpoints, `/tasks/summary`, and any change to the contract, models, store, `main.py`, `conftest.py`, `pyproject.toml` or CI.

### Assumptions

- **A1.** Updating the contract's "Current status" row for these endpoints is out of scope (the ticket forbids contract changes); it stays accurate while the flag is off. Follow-up below.
- **A2.** The flag is read on every request, not at import, so tests and operators can flip it without reloading the module.

## 3. Current state (verified)

- `app/routes/tasks.py`: `list_tasks(status: TaskStatus = TaskStatus.all, store = Depends(get_store))` and `create_task(body: TaskCreate, store = Depends(get_store))`, `status_code=201`, both `raise HTTPException(501, "Not implemented")`. FastAPI validates the query and body before the handler runs, so the 422s already work.
- `app/store.py`: `list()` reverses insertion order then does a stable sort by `created_at` descending, which gives exactly AC1's tie rule. `add()` stamps `created_at` from the injected clock (`datetime.now(UTC)` by default).
- `app/models.py`: `TaskCreate` has `extra="forbid"`, `TitleStr` strips then checks 1–200, `NotesStr` max 2,000, `due: date | None`. `UtcDateTime` serialises as `%Y-%m-%dT%H:%M:%S.%fZ`.
- `tests/conftest.py`: `store` fixture (fresh `TaskStore()`), `client` fixture overriding `get_store` with it. `tests/test_store.py` has a `ticking_clock` helper and overrides `store` locally — the pattern to follow.

## 4. Proposed design

| File | Change |
|---|---|
| `app/routes/tasks.py` | Add the flag check; `list_tasks` returns `store.list(status)`; `create_task` returns `store.add(body)` |
| `tests/test_tasks.py` | Replace the 501 tests with AC1–AC4 and D1 tests |

The flag, in `app/routes/tasks.py`:

```python
FLAG = "TASKS_LIST_CREATE_ENABLED"

def _enabled() -> bool:
    return os.environ.get(FLAG, "").strip().lower() in {"1", "true", "yes", "on"}
```

Each handler starts with `if not _enabled(): raise HTTPException(status_code=501, detail="Not implemented")`, then delegates. Keep it inside the handler (not a router dependency) so FastAPI's validation still runs first and gives 422 whether the flag is on or off, as the contract says for stubs.

No new models, no new errors: every 422 comes from the existing models.

## 5. Key decisions

| Decision | Choice | Rationale | Alternatives rejected |
|---|---|---|---|
| Flag mechanism | Env var read per request in `tasks.py` | No flag service or settings module exists; the ticket allows changes only in `tasks.py` | A settings module (touches files outside scope); a router-level dependency (runs before/alongside validation, would blur 501 vs 422) |
| Logic location | Delegate to `TaskStore` | Ordering, filtering and creation are already implemented and tested there | Re-sorting in the route (duplicates store logic) |

## 6. Implementation tasks

### T1. Build GET and POST /tasks behind the flag (S)

- Goal: AC1–AC5 and D1.
- Changes: `app/routes/tasks.py`, `tests/test_tasks.py`.
- Details:
  - In `tests/test_tasks.py`, override the `store` fixture with `TaskStore(clock=...)` so `created_at` is controlled (follow `ticking_clock` in `tests/test_store.py`; copy the small helper rather than importing from another test module). Seed with `store.add(TaskCreate(...))`; mark done with `store.update(id, TaskUpdate(done=True))`.
  - An autouse fixture sets the flag with `monkeypatch.setenv("TASKS_LIST_CREATE_ENABLED", "1")`; the D1 test uses `monkeypatch.delenv(..., raising=False)`.
  - For the AC1 tie rule, use a clock that returns the same instant for several tasks.
  - For AC3's "now", use the default-clock `store` or a fixed clock and assert `created_at` equals the clock's value in the `.ffffffZ` shape; assert `id` parses as a UUID and that the task is then in `GET /tasks`.
- Done when: all tests below pass; `ruff check .`, `ruff format --check .` and `pytest` pass locally and in CI.
- Tests: see section 7.
- Depends on: none.

## 7. Test strategy

All API tests through the `client` fixture (TestClient), in `tests/test_tasks.py`.

| AC | What the test verifies |
|---|---|
| AC1 | Empty store → 200 `[]`. Three tasks at ticking times → returned newest first. Three tasks at the same instant → latest added first. Mixed: equal and different times together |
| AC2 | Two open + one done: `open` → the two open, `done` → the one, `all` and no param → all three (still newest first). `status=later` and `status=OPEN` → 422 |
| AC3 | `{"title": "  Buy milk  "}` → 201, `title == "Buy milk"`, `notes == ""`, `due is None`, `done is False`, `done_at is None`, `UUID(id)` valid, `created_at` exactly the clock's value as `YYYY-MM-DDTHH:MM:SS.ffffffZ` (including a whole-second case → `.000000Z`). With `notes` and `due` sent, they are echoed. Two posts → distinct ids |
| AC4 | Parametrised 422 cases: `{}`; `{"title": "   "}`; title of 201 chars (200 → 201); notes of 2,001 chars (2,000 → 201); `due` = `"23/11/2026"`, `"2026-13-01"`, `"tomorrow"`; extra `"id"`, `"created_at"`, `"done_at"`, `"done"`, `"priority"`. Each also leaves the store empty |
| AC5 | The 501 tests are removed; CI green |
| D1 | Flag unset → both endpoints 501 `{"detail": "Not implemented"}`; `status=later` and a blank title still 422 |

Regression risk: low. `test_store.py`, `test_task.py`, `test_summary.py` are untouched; `test_health.py`'s OpenAPI path test is unaffected because routes don't change.

## 8. Rollout and rollback

**Feature flag:** `TASKS_LIST_CREATE_ENABLED`, an environment variable, off by default (unset). Off: both endpoints answer 501 as today. On (`1`/`true`/`yes`/`on`): they work. Turn on by starting the server with `TASKS_LIST_CREATE_ENABLED=1 uvicorn app.main:app`. No migrations, no config files. Rollback: unset the flag, or revert the merge commit.

## 9. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Web app developers don't know to set the flag and see 501 | Medium | Confusion | PR body and follow-up name the flag; README update in the follow-up |
| Flag check placed before validation turns 422s into 501 | Low | Contract broken | D1 test asserts 422 with flag off |

## 10. Technical debt

Taken on: the flag lives in a route module (code debt). Remove it, with its tests, once the endpoints are on for good.

## 11. Open questions

| # | Question | Who can answer | Blocks | Assumption made |
|---|---|---|---|---|
| Q1 | Is an env-var flag off by default right, given the contract may be updated to "Built" later? | Plan gate | No | Yes (section 8) |

## 12. Follow-ups

- Mark `GET /tasks`, `POST /tasks` as built in the contract's status table and name the flag in the README (outside this ticket's files).
- Remove `TASKS_LIST_CREATE_ENABLED` once enabled everywhere.
