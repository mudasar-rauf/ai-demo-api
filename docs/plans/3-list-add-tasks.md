# Technical Plan: #3 List and add tasks

**Ticket:** #3   **Spec:** [docs/specs/3-list-add-tasks.md](../specs/3-list-add-tasks.md)   **Status:** Draft (rework 1, after the plan gate)

## 1. Summary

`GET /tasks` and `POST /tasks` are wired in `app/routes/tasks.py` but answer 501. The store (`app/store.py`) already does the work: `TaskStore.list(status)` filters and sorts newest first, and `TaskStore.add(data)` makes the id, `created_at`, `done=False` and `done_at=None`. The models (`app/models.py`) already enforce every 422 of AC2 and AC4. So the change is to make both handlers delegate to the store and to replace the 501 tests with behaviour tests. No feature flag: the scaffold's 501 is the off state, and merging is the release. One task, size S.

## 2. Requirements

### Acceptance criteria

| ID | Criterion (short) | Source |
|---|---|---|
| AC1 | `GET /tasks` → 200, newest first; same `created_at` → latest created first | ticket |
| AC2 | `status=open` / `done` filter; `all` or none → every task; other → 422 | ticket |
| AC3 | `POST /tasks` → 201 with trimmed title, defaults, `done=false`, `done_at=null`, new UUID, `created_at` now as `…​.ffffffZ` | ticket |
| AC4 | `POST /tasks` → 422 for missing/blank/over-200 title, over-2,000 notes, bad `due`, any extra field incl. `id`, `created_at`, `done_at` | ticket |
| AC5 | `tests/test_tasks.py` covers AC1–AC4 instead of the 501 checks, seeding through the store; Ruff and pytest pass in CI | ticket |

### Out of scope

`/tasks/{id}` endpoints, `/tasks/summary`, and any change to the contract, models, store, `main.py`, `conftest.py`, `pyproject.toml` or CI.

### Assumptions

- **A1.** Updating the contract's "Current status" row for these endpoints is out of scope (the ticket forbids contract changes). Follow-up below.
- **A2.** The API is single-user, with no sign-in or ownership, as the contract says (confirmed at the plan gate).

## 3. Current state (verified)

- `app/routes/tasks.py`: `list_tasks(status: TaskStatus = TaskStatus.all, store = Depends(get_store))` and `create_task(body: TaskCreate, store = Depends(get_store))`, `status_code=201`, both `raise HTTPException(501, "Not implemented")`. FastAPI validates the query and body before the handler runs, so the 422s already work.
- `app/store.py`: `list()` reverses insertion order then does a stable sort by `created_at` descending, which gives exactly AC1's tie rule. `add()` stamps `created_at` from the injected clock (`datetime.now(UTC)` by default).
- `app/models.py`: `TaskCreate` has `extra="forbid"`, `TitleStr` strips then checks 1–200, `NotesStr` max 2,000, `due: DueDate | None`, where `DueDate` (from #9, merged in 8af616f) accepts only a `YYYY-MM-DD` string, refusing numbers and numeric strings that Pydantic would otherwise read as Unix times. `UtcDateTime` serialises as `%Y-%m-%dT%H:%M:%S.%fZ`.
- `tests/conftest.py`: `store` fixture (fresh `TaskStore()`), `client` fixture overriding `get_store` with it. `tests/test_store.py` has a `ticking_clock` helper and overrides `store` locally — the pattern to follow.

## 4. Proposed design

| File | Change |
|---|---|
| `app/routes/tasks.py` | `list_tasks` returns `store.list(status)`; `create_task` returns `store.add(body)` |
| `tests/test_tasks.py` | Replace the 501 tests with AC1–AC4 tests |

No new models, no new errors: every 422 comes from the existing models.

## 5. Key decisions

| Decision | Choice | Rationale | Alternatives rejected |
|---|---|---|---|
| Logic location | Delegate to `TaskStore` | Ordering, filtering and creation are already implemented and tested there | Re-sorting in the route (duplicates store logic) |

## 6. Implementation tasks

### T1. Build GET and POST /tasks (S)

- Goal: AC1–AC5.
- Changes: `app/routes/tasks.py`, `tests/test_tasks.py`.
- Details:
  - In `tests/test_tasks.py`, override the `store` fixture with `TaskStore(clock=...)` so `created_at` is controlled (follow `ticking_clock` in `tests/test_store.py`; copy the small helper rather than importing from another test module). Seed with `store.add(TaskCreate(...))`; mark done with `store.update(id, TaskUpdate(done=True))`.
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
| AC4 | Parametrised 422 cases: `{}`; `{"title": "   "}`; title of 201 chars (200 → 201); notes of 2,001 chars (2,000 → 201); `due` = `"23/11/2026"`, `"2026-13-01"`, `"tomorrow"`, the number `1763856000` and the numeric string `"1763856000"` (the #9 cases, now refused by `TaskCreate`); extra `"id"`, `"created_at"`, `"done_at"`, `"done"`, `"priority"`. Each also leaves the store empty |
| AC5 | The 501 tests are removed; CI green |

Regression risk: low. `test_store.py`, `test_task.py`, `test_summary.py` are untouched; `test_health.py`'s OpenAPI path test is unaffected because routes don't change.

## 8. Rollout and rollback

**Feature flag:** none, by the plan gate's decision recorded in #3: until this issue is merged, the scaffold's 501 is the off state, and merging it is the release. No migrations, no config. Rollback: revert the merge commit, which brings back the 501s.

## 9. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| A client relies on the 501s | Low | Behaviour change on merge | The contract already describes these endpoints; merging is the intended release |
| `due` tests drift from the model | Low | AC4 gaps | Numeric and numeric-string `due` cases are in the AC4 parametrised list |

## 10. Technical debt

None taken on.

## 11. Open questions

None. The plan gate answered the architect's question: the API is single-user, with no sign-in or ownership.

## 12. Rework log

Plan gate, rejected (mudasar-rauf):

1. **Architect M1, no feature flag.** Dropped `TASKS_LIST_CREATE_ENABLED`, its helper, its tests and the derived D1 from the spec and this plan. Section 8 records the decision.
2. **Architect M2, #9 merged.** Merged `origin/main` (8af616f) into this branch. Section 3 notes `DueDate`; section 7's AC4 cases now include a numeric `due` (`1763856000`) and a numeric string (`"1763856000"`), both 422. `app/models.py` is not changed.
3. **Architect's question.** Single-user, no sign-in or ownership; recorded as A2 and in the spec.

## 13. Follow-ups

- Mark `GET /tasks`, `POST /tasks` as built in the contract's status table (outside this ticket's files).
