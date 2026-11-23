# Technical Plan: #5 The summary of the tasks

**Ticket:** #5   **Spec:** [docs/specs/5-tasks-summary.md](../specs/5-tasks-summary.md)   **Status:** Draft (rework after the plan gate)

## 0. Rework

The plan gate rejected the first plan for one change, the architect's M1: no feature flag. This version:

- drops `TASKS_SUMMARY_ENABLED`, its `summary_enabled()` helper, its tests and the derived AC5;
- drops the architect's m1 and m2, which were about the flag;
- records the gate's answer to the architect's question: the API is single-user, with no sign-in or ownership, as the contract says. "Every task" in AC1 means every task in the store.

Everything else stands as before.

## 1. Summary

`GET /tasks/summary` is wired and answers 501. The store already counts the tasks (`TaskStore.summary()`), and the `Summary` model already matches the contract. This issue replaces the stub's body in `app/routes/summary.py` with `return store.summary()`. `tests/test_summary.py` replaces its 501 check with tests for AC1 to AC3. Two files change; nothing else.

## 2. Requirements

### Acceptance criteria

| ID | Criterion | Source |
|---|---|---|
| AC1 | `GET /tasks/summary` answers 200 with `total`, `open` and `done`, counting every task; `total` is `open + done` | ticket |
| AC2 | With no tasks it answers `{"total": 0, "open": 0, "done": 0}` | ticket |
| AC3 | `/tasks/summary` is never read as a task id: never a 404 or a 422 | ticket |
| AC4 | `tests/test_summary.py` covers AC1 to AC3 in place of its 501 check, seeding through the store, done and not done; Ruff and pytest pass in CI | ticket |

### Non-functional requirements

- No new dependency (pyproject pins are fixed by #1's AC6).
- The count is consistent: `TaskStore.summary()` takes the store's lock, so `total == open + done` even under concurrent writes.

### Out of scope

Listing, adding, changing or deleting tasks; `docs/contracts/api.md`, `app/models.py`, `app/store.py`, `app/main.py`.

### Assumptions

- A1. The API is single-user, with no sign-in or ownership (confirmed at the plan gate), so the summary counts every task in the store.

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
| `app/routes/summary.py` | `task_summary` returns `store.summary()` instead of raising 501; drop the now-unused `HTTPException` import | Modified |
| `tests/test_summary.py` | Replace the 501 test with the tests in section 7 | Modified |

### APIs and contracts

Unchanged from `docs/contracts/api.md`: `GET /tasks/summary`, no request, `200 Summary`, no errors.

### Error handling and edge cases

- Empty store: `Summary(0, 0, 0)` (AC2).
- Routing: no change; the router order in `main.py` already keeps `summary` from reaching `/tasks/{task_id}` (AC3). A test pins it.

## 5. Key decisions

| Decision | Choice | Rationale | Alternatives rejected |
|---|---|---|---|
| Where counting happens | `store.summary()` | Already built, tested and atomic under the lock | Counting `store.list()` in the route: duplicates logic, two passes, out of scope to change the store |
| Release control | None: merging is the release | Decided at the plan gate; the scaffold's 501 is the off state until merge | An env-var flag (the first plan): rejected at the gate |

No ADR: nothing here is hard to reverse or crosses a module boundary.

## 6. Implementation tasks

### T1. Summary endpoint, with tests (S)

- Goal: AC1 to AC4.
- Changes: `app/routes/summary.py`, `tests/test_summary.py`.
- Details: write the tests first (section 7), then the route. Keep the existing signature and `response_model`. Seed tests through the `store` fixture: `store.add(TaskCreate(title=...))` and `store.update(id, TaskUpdate(done=True))`.
- Done when: the tests in section 7 pass; `ruff check .`, `ruff format --check .` and `pytest` pass locally and in CI.
- Depends on: none.

### Sequence

One task, size S.

## 7. Test strategy

All API tests in `tests/test_summary.py`, through `client`, with tasks seeded through `store`.

| AC | Test | What it verifies |
|---|---|---|
| AC1 | `test_counts_open_and_done` | 3 tasks, 1 marked done: 200 and `{"total": 3, "open": 2, "done": 1}`; `total == open + done` |
| AC1 | `test_counts_every_task_when_all_done` | 2 tasks both done: `{"total": 2, "open": 0, "done": 2}` |
| AC1 | `test_counts_follow_undone` | A task done then undone counts as open |
| AC2 | `test_empty_store` | No tasks: 200 and exactly `{"total": 0, "open": 0, "done": 0}` |
| AC3 | `test_summary_is_not_a_task_id` | Status is 200, so neither 404 nor 422 |
| AC4 | CI | Ruff and pytest green on the PR |

Regression risk: low. `tests/test_store.py::TestSummary` already covers the counting. The other route tests are untouched.

## 8. Rollout and rollback

- **Feature flag:** none, by decision at the plan gate. Until merge, the scaffold's 501 is the off state; merging is the release.
- No migrations, no config files, no contract change.
- Rollback: revert the merge commit, which restores the 501.

## 9. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Someone reorders routers in `main.py` and `summary` becomes a 422 | Low | AC3 broken | `test_summary_is_not_a_task_id` fails |

## 10. Technical debt

None taken on.

## 11. Open questions

| # | Question | Who can answer | Blocks | Assumption made |
|---|---|---|---|---|
| Q1 | Should the contract's "Current status" row for `/tasks/summary` change to "Built"? The ticket rules out contract changes. | Maintainer | No | No; a follow-up updates it |

## 12. Follow-ups

- Mark `GET /tasks/summary` as Built in `docs/contracts/api.md`.
