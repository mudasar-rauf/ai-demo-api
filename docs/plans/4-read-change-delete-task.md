# Technical Plan: #4 Read, change and delete one task

**Ticket:** #4   **Spec:** [docs/specs/4-read-change-delete-task.md](../specs/4-read-change-delete-task.md)   **Status:** Draft

## 1. Summary

Fill in the three stubs in `app/routes/task.py` (`GET`, `PATCH`, `DELETE /tasks/{task_id}`) so they call the existing `TaskStore.get`, `update` and `delete`, and answer 404 `{"detail": "Task not found"}` when the store has no such task. The store already holds the `done_at` rule (AC3) and the models already hold every 422 rule (AC2), so the route code is a few lines each. The endpoints sit behind the environment variable `TASK_ENDPOINTS_ENABLED`, off by default, which keeps today's 501. `tests/test_task.py` replaces its 501 checks with tests of AC1 to AC4.

## 2. Requirements

### Acceptance criteria

| ID | Criterion | Source |
|---|---|---|
| AC1 | `GET /tasks/{id}`: 200 with the task; unknown id 404 `{"detail": "Task not found"}`; non-UUID 422 | ticket |
| AC2 | `PATCH /tasks/{id}`: only sent fields change, 200 with the changed task; `{}` changes nothing; `due: null` clears; null `title`/`notes`/`done`, a broken rule or any other field (`id`, `created_at`, `done_at`) is 422; unknown id 404 | ticket |
| AC3 | `done` false→true sets `done_at` to now; true→false sets `null`; same value leaves `done_at` | ticket |
| AC4 | `DELETE /tasks/{id}`: 204 no body, a later GET is 404; unknown id 404; non-UUID 422 | ticket |
| AC5 | `tests/test_task.py` covers AC1–AC4 in place of its 501 checks, seeding through the store; Ruff and pytest pass in CI | ticket |
| AC6 | Behind `TASK_ENDPOINTS_ENABLED`, off by default; off answers 501 after input validation | derived (factory feature-flag rule) |

### Non-functional requirements

- Response bodies follow the contract exactly; date-times serialise through `UtcDateTime` (already in `Task`), so nothing extra is needed.
- No change to the contract, models or store (ticket's "Not in this issue").

### Out of scope

`GET /tasks`, `POST /tasks`, `GET /tasks/summary`; any change to `docs/contracts/api.md`, `app/models.py`, `app/store.py`.

### Assumptions

- A1. "Now" in AC3 is the store's clock (`TaskStore(clock=...)`, default `datetime.now(UTC)`). Tests inject a fixed clock to assert it exactly.
- A2. A PATCH of an unknown id with an invalid body is a 422, not a 404: FastAPI validates the body before the handler runs. The contract does not order the two; this is FastAPI's natural behaviour.
- A3. The flag is read on every request (not at import), so tests can switch it with `monkeypatch.setenv` and operators without a code change.

## 3. Current state

- `app/routes/task.py`: three handlers, each `raise HTTPException(status_code=501, detail="Not implemented")`. Signatures already take `task_id: UUID`, `body: TaskUpdate` and `store: TaskStore = Depends(get_store)`; DELETE is declared `status_code=204, response_class=Response`.
- `app/store.py`: `TaskStore.get(id) -> Task | None`, `update(id, TaskUpdate) -> Task | None` (applies `model_dump(exclude_unset=True)`; sets/clears `done_at` only when `done` actually changes, using `self._clock()`), `delete(id) -> bool`. All under one lock.
- `app/models.py`: `TaskUpdate` has `extra="forbid"`, non-nullable `title`/`notes`/`done` (explicit `null` → 422), nullable `due`; `TitleStr` trims and is 1–200 chars; `NotesStr` ≤ 2000.
- `tests/conftest.py`: `store` fixture (fresh `TaskStore()`) and `client` fixture that overrides `get_store` with it.
- `tests/test_task.py`: three 501 checks, a null-field 422 check and a non-UUID 422 check.
- No feature-flag service or flag module exists in the repo.

## 4. Proposed design

### Changes by component

| File | Change | New or modified |
|---|---|---|
| `app/routes/task.py` | Flag helper; real bodies for the three handlers | Modified |
| `tests/test_task.py` | Replace 501 checks with AC1–AC4 tests; add flag-off tests | Modified |

### Contract of each handler (`app/routes/task.py`)

```python
FLAG = "TASK_ENDPOINTS_ENABLED"
NOT_FOUND = "Task not found"

def _enabled() -> bool:           # os.environ.get(FLAG, "").lower() == "true"
def _require_enabled() -> None:   # raise HTTPException(501, "Not implemented") when off
```

- `get_task`: `_require_enabled()`; `task = store.get(task_id)`; `None` → `HTTPException(404, NOT_FOUND)`; else return it.
- `update_task`: `_require_enabled()`; `task = store.update(task_id, body)`; `None` → 404; else return it. Pass `body` as is: the store reads `exclude_unset`, so `{}` changes nothing and `due: null` clears.
- `delete_task`: `_require_enabled()`; `store.delete(task_id)` false → 404; else `return Response(status_code=204)` (or return `None` with the declared `status_code=204`; either gives an empty body).

The flag check must be the first line of the handler body, **not** a `Depends`: FastAPI runs dependencies before it reports body validation errors, so a dependency raising 501 would hide the 422s the contract promises while a stub is off.

### Error handling

| Case | Answer | Where it comes from |
|---|---|---|
| Non-UUID id | 422 | `task_id: UUID` path param |
| Null `title`/`notes`/`done`, extra field, broken rule | 422 | `TaskUpdate` |
| Unknown id | 404 `{"detail": "Task not found"}` | handler |
| Flag off | 501 `{"detail": "Not implemented"}` | handler |

## 5. Key decisions

| Decision | Choice | Rationale | Alternatives rejected |
|---|---|---|---|
| Feature flag | Env var `TASK_ENDPOINTS_ENABLED`, `true` enables, anything else off | No flag service in the repo; env var needs no new file, stays within the ticket's two files | Config file / settings module: adds a file outside the ticket's list |
| Off state | 501 `Not implemented` | Matches the contract's "501 until its issue lands"; web app sees no change while off | 404: would read as "task not found" to the web app |
| Where to check the flag | Handler body | Keeps 422-before-501 (see §4) | `Depends(...)`: masks body 422s |
| `done_at` logic | Reuse `TaskStore.update` | Already implemented and tested in `tests/test_store.py` | Duplicating in the route |

No ADR needed.

## 6. Implementation tasks

### T1. Build the three handlers behind the flag, test-first (S)

- Goal: AC1–AC6.
- Changes: `app/routes/task.py`, `tests/test_task.py`.
- Details:
  - In `tests/test_task.py`, add a module-level autouse fixture that sets `TASK_ENDPOINTS_ENABLED=true` with `monkeypatch.setenv`, except in the flag-off tests (use a marker or set `monkeypatch.delenv` inside those tests).
  - Override the `store` fixture locally with `TaskStore(clock=...)` returning a fixed or stepping UTC time, so `done_at` can be asserted exactly. Seed with `store.add(TaskCreate(...))` and `store.update(...)`; never through `POST /tasks` (it is still a stub).
  - Assert date-times in their wire shape (`...Z`, six fractional digits).
- Done when: every test in §7 passes; `ruff check .`, `ruff format --check .` and `pytest` pass locally and in CI.
- Tests: see §7.
- Depends on: none.

### Sequence

One task, size S.

## 7. Test strategy

All in `tests/test_task.py`, through `TestClient` (integration tests at the HTTP boundary; the store's own logic is already covered by `tests/test_store.py`).

| AC | Test type | What the test verifies |
|---|---|---|
| AC1 | integration | Seeded task → 200, body equals the task as JSON; random UUID → 404 `{"detail": "Task not found"}`; `/tasks/not-a-uuid` → 422 |
| AC2 | integration | Each of `title` (trimmed), `notes`, `due`, `done` changes alone, others unchanged; `{}` → 200, task unchanged; `due: null` clears; null `title`/`notes`/`done` → 422 (keep the existing parametrised test); `title: "   "`, 201-char title, 2001-char notes, `due: "23-11-2026"` → 422; `id`, `created_at`, `done_at`, `foo` → 422 and the stored task unchanged; unknown id → 404 |
| AC3 | integration | false→true sets `done_at` to the clock's time; true→false sets `null`; true→true keeps the earlier `done_at` (clock advanced between calls); false→false keeps `null` |
| AC4 | integration | Seeded task → 204, empty body, later GET 404; unknown → 404; non-UUID → 422 |
| AC5 | CI | The 501 checks are gone; CI green |
| AC6 | integration | Flag unset: GET/PATCH/DELETE on a seeded id → 501 `Not implemented`, task still in the store; non-UUID and `{"title": null}` still 422 |

Regression risk: `tests/test_tasks.py` and `tests/test_summary.py` still expect 501 for their own endpoints; this change does not touch them.

## 8. Rollout and rollback

- **Feature flag:** `TASK_ENDPOINTS_ENABLED`, an environment variable, off by default (unset or any value other than `true`). Turn on by setting it to `true` for the `uvicorn` process; turn off by unsetting it and restarting. While off, the endpoints answer 501 exactly as today.
- No migrations, no configuration files, no infrastructure. The service is not deployed anywhere yet.
- Rollback: unset the flag; or revert the merge commit.
- Follow-up when the flag is retired: remove the check and the flag-off tests, and update the contract's "Current status" table (left untouched here because the ticket forbids contract changes).

## 9. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Flag left on in a test leaks to other test modules | Low | Medium | Use `monkeypatch` only; it restores the environment after each test |
| Flag checked in a dependency, hiding 422s | Low | Medium | §4 says handler body; AC6 test checks 422 while off |
| `done_at` asserted with a real clock, flaky | Medium | Low | Inject a clock into the local `store` fixture |

## 10. Technical debt

- Taken on (documentation): the contract's "Current status" table will still say 501 after merge, since the ticket rules out contract changes. Follow-up: update it when the flag is removed.

## 11. Open questions

| # | Question | Who can answer | Blocks | Assumption made |
|---|---|---|---|---|
| Q1 | Is an env var named `TASK_ENDPOINTS_ENABLED` with 501 while off acceptable as this issue's feature flag? | Plan gate | No | Yes (§8) |

## 12. Follow-ups

- Update `docs/contracts/api.md` "Current status" once the endpoints are on for good, and retire the flag.
