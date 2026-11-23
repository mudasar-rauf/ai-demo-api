# Technical Plan: #5 The summary of the tasks

**Ticket:** #5   **Spec:** [docs/specs/5-tasks-summary.md](../specs/5-tasks-summary.md)   **Status:** Draft

## 1. Summary

`GET /tasks/summary` is wired and answers 501. The store already counts the tasks (`TaskStore.summary()`), and the `Summary` model already matches the contract. This issue replaces the stub's body in `app/routes/summary.py` with a call to `store.summary()`, behind the environment variable `TASKS_SUMMARY_ENABLED` (off by default, so the endpoint keeps answering 501 until the flag is set). `tests/test_summary.py` replaces its 501 check with tests for AC1 to AC3 and the flag (AC5). Two files change; nothing else.

## 2. Requirements

### Acceptance criteria

| ID | Criterion | Source |
|---|---|---|
| AC1 | `GET /tasks/summary` answers 200 with `total`, `open` and `done`, counting every task; `total` is `open + done` | ticket |
| AC2 | With no tasks it answers `{"total": 0, "open": 0, "done": 0}` | ticket |
| AC3 | `/tasks/summary` is never read as a task id: never a 404 or a 422 | ticket |
| AC4 | `tests/test_summary.py` covers AC1 to AC3 in place of its 501 check, seeding through the store, done and not done; Ruff and pytest pass in CI | ticket |
| AC5 | Behind `TASKS_SUMMARY_ENABLED`, off by default; off answers `501 {"detail": "Not implemented"}`; on only for `1` or `true`, any case | derived (factory flag rule) |

### Non-functional requirements

- No new dependency (pyproject pins are fixed by #1's AC6). The flag uses `os.environ`.
- The count is consistent: `TaskStore.summary()` takes the store's lock, so `total == open + done` even under concurrent writes.

### Out of scope

Listing, adding, changing or deleting tasks; `docs/contracts/api.md`, `app/models.py`, `app/store.py`, `app/main.py`.

### Assumptions

- A1. The flag reuses the current 501 body as its "off" state. This keeps the contract's "Current status" row true while the flag is off, and keeps AC3 (never 404 or 422) true in both states.
- A2. The flag is read on every request, not at import, so tests can switch it with `monkeypatch.setenv` and an operator can enable it with a restart-free env change where the process manager allows. The cost is one dict lookup per request.

## 3. Current state

- `app/routes/summary.py`: `task_summary(store: TaskStore = Depends(get_store)) -> Summary` raises `HTTPException(501, "Not implemented")`. `response_model=Summary`.
- `app/main.py`: includes `summary.router` before `tasks.router` and `task.router`, with a comment saying why. `/tasks/{task_id}` takes a `UUID`, so `summary` would be a 422 there if the order ever changed.
- `app/store.py`: `TaskStore.summary()` returns `Summary(total, open=total - done, done)` under the lock; tested in `tests/test_store.py::TestSummary`.
- `tests/conftest.py`: the `store` fixture is a fresh `TaskStore`; `client` overrides `get_store` with it, so a test seeds tasks with `store.add(...)` and `store.update(...)` and reads them through `client`.
- `tests/test_summary.py`: one test asserting 501.

## 4. Proposed design

### Changes by component

| File | Change | New or modified |
|---|---|---|
| `app/routes/summary.py` | Add `SUMMARY_FLAG = "TASKS_SUMMARY_ENABLED"` and `summary_enabled() -> bool`; `task_summary` raises the existing 501 when the flag is off, else returns `store.summary()` | Modified |
| `tests/test_summary.py` | Replace the 501 test with the tests in section 7 | Modified |

### APIs and contracts

Unchanged from `docs/contracts/api.md`: `GET /tasks/summary`, no request, `200 Summary`, no errors.

```python
SUMMARY_FLAG = "TASKS_SUMMARY_ENABLED"

def summary_enabled() -> bool:
    return os.environ.get(SUMMARY_FLAG, "").strip().lower() in {"1", "true"}
```

### Error handling and edge cases

- Empty store: `Summary(0, 0, 0)` (AC2).
- Flag unset, empty, `0`, `false`, or anything else: 501 (AC5).
- Routing: no change; the router order in `main.py` already keeps `summary` from reaching `/tasks/{task_id}` (AC3). A test pins it.

## 5. Key decisions

| Decision | Choice | Rationale | Alternatives rejected |
|---|---|---|---|
| Where counting happens | `store.summary()` | Already built, tested and atomic under the lock | Counting `store.list()` in the route: duplicates logic, two passes, out of scope to change the store |
| Flag mechanism | Env var read per request in `summary.py` | No flag service is linked; the ticket limits changes to two files; per-request read is testable with `monkeypatch` | A settings module or a check in `main.py`: touches files the ticket excludes; reading at import makes tests depend on import order |
| Flag-off behaviour | The existing 501 | Matches the contract's status table and keeps AC3 | 404: breaks AC3 |

No ADR: nothing here is hard to reverse or crosses a module boundary.

## 6. Implementation tasks

### T1. Summary endpoint behind its flag, with tests (S)

- Goal: AC1 to AC5.
- Changes: `app/routes/summary.py`, `tests/test_summary.py`.
- Details: write the tests first (section 7), then the route. Keep the existing signature and `response_model`. Use `os.environ.get`, not a cached value. Seed tests through the `store` fixture: `store.add(TaskCreate(title=...))` and `store.update(id, TaskUpdate(done=True))`. Set the flag with `monkeypatch.setenv(SUMMARY_FLAG, "1")`; a small autouse-free fixture such as `enabled` keeps it explicit.
- Done when: the tests in section 7 pass; `ruff check .`, `ruff format --check .` and `pytest` pass locally and in CI.
- Depends on: none.

### Sequence

One task, size S.

## 7. Test strategy

All API tests in `tests/test_summary.py`, through `client`, with tasks seeded through `store`.

| AC | Test | What it verifies |
|---|---|---|
| AC1 | `test_counts_open_and_done` | Flag on; 3 tasks, 1 marked done: 200 and `{"total": 3, "open": 2, "done": 1}`; `total == open + done` |
| AC1 | `test_counts_every_task_when_all_done` | Flag on; 2 tasks both done: `{"total": 2, "open": 0, "done": 2}` |
| AC1 | `test_counts_follow_undone` | Flag on; a task done then undone counts as open |
| AC2 | `test_empty_store` | Flag on; no tasks: exactly `{"total": 0, "open": 0, "done": 0}` |
| AC3 | `test_summary_is_not_a_task_id` | Flag on and flag off: status is neither 404 nor 422 |
| AC5 | `test_off_by_default` | Flag unset (`monkeypatch.delenv(..., raising=False)`): `501 {"detail": "Not implemented"}` |
| AC5 | `test_flag_values` | Parametrised: `1`, `true`, `TRUE` → 200; `0`, `false`, `""`, `yes` → 501 |
| AC4 | CI | Ruff and pytest green on the PR |

Regression risk: low. `tests/test_store.py::TestSummary` already covers the counting. The other route tests are untouched.

## 8. Rollout and rollback

- **Feature flag:** `TASKS_SUMMARY_ENABLED`, an environment variable, off by default. Off: 501, as today. On: set `TASKS_SUMMARY_ENABLED=1` in the server's environment and restart `uvicorn` (or not, since it is read per request).
- No migrations, no config files, no contract change.
- Rollback: unset the variable; or revert the merge commit.
- Follow-up once released: remove the flag (see section 12).

## 9. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Someone reorders routers in `main.py` and `summary` becomes a 422 | Low | AC3 broken | `test_summary_is_not_a_task_id` fails |
| Flag left on in a shell that runs tests, masking the off-default test | Low | False pass | Tests set or delete the variable explicitly with `monkeypatch` |
| Web app expects 200 while the flag is off | Medium | Web app shows an error | The contract already says 501 until built; README/PR note says how to enable |

## 10. Technical debt

Taken on: the flag itself (code debt), to be removed once the endpoint is released.

## 11. Open questions

| # | Question | Who can answer | Blocks | Assumption made |
|---|---|---|---|---|
| Q1 | Should the contract's "Current status" row for `/tasks/summary` change to "Built" in this issue? The ticket rules out contract changes. | Plan gate | No | No; update it when the flag is removed |

## 12. Follow-ups

- Remove `TASKS_SUMMARY_ENABLED` and mark `GET /tasks/summary` as Built in `docs/contracts/api.md`.
