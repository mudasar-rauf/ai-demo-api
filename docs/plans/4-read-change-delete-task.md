# Technical Plan: #4 Read, change and delete one task

**Ticket:** #4   **Spec:** [docs/specs/4-read-change-delete-task.md](../specs/4-read-change-delete-task.md)   **Status:** Draft (rework 1 after the plan gate)

## 1. Summary

Fill in the three stubs in `app/routes/task.py` (`GET`, `PATCH`, `DELETE /tasks/{task_id}`) so they call the existing `TaskStore.get`, `update` and `delete`, and answer 404 `{"detail": "Task not found"}` when the store has no such task. The store already holds the `done_at` rule (AC3) and the models already hold every 422 rule (AC2), so the route code is a few lines each. There is no feature flag: until this issue is merged the scaffold's 501 is the off state, and merging it is the release. `tests/test_task.py` replaces its 501 checks with tests of AC1 to AC4.

## 2. Requirements

### Acceptance criteria

| ID | Criterion | Source |
|---|---|---|
| AC1 | `GET /tasks/{id}`: 200 with the task; unknown id 404 `{"detail": "Task not found"}`; non-UUID 422 | ticket |
| AC2 | `PATCH /tasks/{id}`: only sent fields change, 200 with the changed task; `{}` changes nothing; `due: null` clears; a numeric `due` (`1763856000` or `"1763856000"`) is 422 (since #9); null `title`/`notes`/`done`, a broken rule or any other field (`id`, `created_at`, `done_at`) is 422; unknown id 404 | ticket |
| AC3 | `done` false→true sets `done_at` to now; true→false sets `null`; same value leaves `done_at` | ticket |
| AC4 | `DELETE /tasks/{id}`: 204 no body, a later GET is 404; unknown id 404; non-UUID 422 | ticket |
| AC5 | `tests/test_task.py` covers AC1–AC4 in place of its 501 checks, seeding through the store; Ruff and pytest pass in CI | ticket |

### Non-functional requirements

- Response bodies follow the contract exactly; date-times serialise through `UtcDateTime` (already in `Task`), so nothing extra is needed.
- No change to the contract, models or store (ticket's "Not in this issue").

### Out of scope

`GET /tasks`, `POST /tasks`, `GET /tasks/summary`; any change to `docs/contracts/api.md`, `app/models.py`, `app/store.py`.

### Assumptions

- A1. "Now" in AC3 is the store's clock (`TaskStore(clock=...)`, default `datetime.now(UTC)`). Tests inject a fixed clock to assert it exactly.
- A2. A PATCH of an unknown id with an invalid body is a 422, not a 404: FastAPI validates the body before the handler runs. The contract does not order the two; this is FastAPI's natural behaviour.

## 3. Current state

- `app/routes/task.py`: three handlers, each `raise HTTPException(status_code=501, detail="Not implemented")`. Signatures already take `task_id: UUID`, `body: TaskUpdate` and `store: TaskStore = Depends(get_store)`; DELETE is declared `status_code=204, response_class=Response`.
- `app/store.py`: `TaskStore.get(id) -> Task | None`, `update(id, TaskUpdate) -> Task | None` (applies `model_dump(exclude_unset=True)`; sets/clears `done_at` only when `done` actually changes, using `self._clock()`), `delete(id) -> bool`. All under one lock.
- `app/models.py`: `TaskUpdate` has `extra="forbid"`, non-nullable `title`/`notes`/`done` (explicit `null` → 422), nullable `due`, which since #9 (merged in 8af616f, merged into this branch) takes only a `YYYY-MM-DD` string or `null`, refusing numbers and numeric strings; `TitleStr` trims and is 1–200 chars; `NotesStr` ≤ 2000.
- `tests/conftest.py`: `store` fixture (fresh `TaskStore()`) and `client` fixture that overrides `get_store` with it.
- `tests/test_task.py`: three 501 checks, a null-field 422 check and a non-UUID 422 check.

## 4. Proposed design

### Changes by component

| File | Change | New or modified |
|---|---|---|
| `app/routes/task.py` | Real bodies for the three handlers | Modified |
| `tests/test_task.py` | Replace 501 checks with AC1–AC4 tests | Modified |

### Contract of each handler (`app/routes/task.py`)

```python
NOT_FOUND = "Task not found"
```

- `get_task`: `task = store.get(task_id)`; `None` → `HTTPException(404, NOT_FOUND)`; else return it.
- `update_task`: `task = store.update(task_id, body)`; `None` → 404; else return it. Pass `body` as is: the store reads `exclude_unset`, so `{}` changes nothing and `due: null` clears.
- `delete_task`: `store.delete(task_id)` false → 404; else `return Response(status_code=204)` (or return `None` with the declared `status_code=204`; either gives an empty body).

### Error handling

| Case | Answer | Where it comes from |
|---|---|---|
| Non-UUID id | 422 | `task_id: UUID` path param |
| Null `title`/`notes`/`done`, extra field, broken rule | 422 | `TaskUpdate` |
| Unknown id | 404 `{"detail": "Task not found"}` | handler |

## 5. Key decisions

| Decision | Choice | Rationale | Alternatives rejected |
|---|---|---|---|
| Feature flag | None | Decided at the plan gate: the six demo issues ship none; the scaffold's 501 is the off state until merge | Env var flag (the first attempt's `TASK_ENDPOINTS_ENABLED`): dropped |
| `done_at` logic | Reuse `TaskStore.update` | Already implemented and tested in `tests/test_store.py` | Duplicating in the route |

No ADR needed.

## 6. Implementation tasks

### T1. Build the three handlers, test-first (S)

- Goal: AC1–AC5.
- Changes: `app/routes/task.py`, `tests/test_task.py`.
- Details:
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
| AC2 | integration | Each of `title` (trimmed), `notes`, `due`, `done` changes alone, others unchanged; `{}` → 200, task unchanged; `due: null` clears; a numeric `due` (`1763856000` or `"1763856000"`) is 422 (since #9); null `title`/`notes`/`done` → 422 (keep the existing parametrised test); `title: "   "`, 201-char title, 2001-char notes, `due: "23-11-2026"`, `due: 1763856000` and `due: "1763856000"` → 422 with the stored `due` unchanged (#9's rule; `app/models.py` is not changed); `id`, `created_at`, `done_at`, `foo` → 422 and the stored task unchanged; unknown id → 404 |
| AC3 | integration | false→true sets `done_at` to the clock's time; true→false sets `null`; true→true keeps the earlier `done_at` (clock advanced between calls); false→false keeps `null` |
| AC4 | integration | Seeded task → 204, empty body, later GET 404; unknown → 404; non-UUID → 422 |
| AC5 | CI | The 501 checks are gone; CI green |

Regression risk: `tests/test_tasks.py` and `tests/test_summary.py` still expect 501 for their own endpoints; this change does not touch them.

## 8. Rollout and rollback

- **Feature flag:** none, by the plan gate's decision for the six demo issues. Until this issue is merged the scaffold's 501 is the off state; merging it is the release.
- No migrations, no configuration files, no infrastructure. The service is not deployed anywhere yet.
- Rollback: revert the merge commit, which brings back the 501 stubs.

## 9. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| `done_at` asserted with a real clock, flaky | Medium | Low | Inject a clock into the local `store` fixture |
| A later change to `due` parsing lets numbers through PATCH | Low | Medium | AC2 tests send `1763856000` and `"1763856000"` and expect 422 |

## 10. Technical debt

- Taken on (documentation): the contract's "Current status" table will still say 501 for these endpoints after merge, since the ticket rules out contract changes. Follow-up below.

## 11. Open questions

None.

## 12. Follow-ups

- Update `docs/contracts/api.md` "Current status" for these three endpoints.

## 13. Rework after the plan gate

The plan gate rejected attempt 1 for two changes; both are made.

1. **No feature flag.** `TASK_ENDPOINTS_ENABLED`, its helpers, its tests and the derived AC6 are gone from the spec and this plan, and with them the architect's flag findings (the 422-before-501 ordering, the flag-off tests). §5 and §8 record the decision.
2. **#9 is merged.** `origin/main` (8af616f) is merged into this branch. AC2's tests (§7) now include a PATCH with `due: 1763856000` and `due: "1763856000"`, each a 422, and keep `due: null` clearing the date. `app/models.py` is not changed.

Everything else in the plan stands.
