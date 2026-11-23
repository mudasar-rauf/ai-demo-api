# Spec: #5 The summary of the tasks

**Ticket:** #5   **Plan:** [docs/plans/5-tasks-summary.md](../plans/5-tasks-summary.md)

## User story

As a person using the Tasks web app, I want to see through the API how many tasks I have, how many are open and how many are done, so that I can tell at a glance how far along I am.

## Outcome

A person can see through the API how many tasks they have, how many are open and how many are done.

## Acceptance criteria

AC1 to AC4 come from the ticket, in its words. None are derived.

- **AC1.** `GET /tasks/summary` answers 200 with `total`, `open` and `done`, counting every task. `total` is `open + done`.
- **AC2.** With no tasks it answers `{"total": 0, "open": 0, "done": 0}`.
- **AC3.** `/tasks/summary` is never read as a task id: it never answers a 404 or a 422.
- **AC4.** `tests/test_summary.py` covers AC1 to AC3 in place of its 501 check, seeding tasks through the store, done and not done. Ruff and pytest pass in CI.

## Files

- `app/routes/summary.py`
- `tests/test_summary.py`

## Out of scope

Listing, adding, changing or deleting tasks, and any change to `docs/contracts/api.md`, the models or the store.

## Release

No feature flag. Until this issue is merged, the scaffold's 501 is the off state, and merging it is the release (decided at the plan gate).
