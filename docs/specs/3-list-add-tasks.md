# Spec: #3 List and add tasks

**Ticket:** #3   **Plan:** [docs/plans/3-list-add-tasks.md](../plans/3-list-add-tasks.md)   **Contract:** [docs/contracts/api.md](../contracts/api.md)

## User story

As a person using the Tasks web app, I want to add a task and list my tasks, all of them or only the open or done ones, newest first, so that I can see what I still have to do and what I have finished.

## Outcome

A person can add a task through the API and list their tasks, all of them or only the open or done ones, newest first.

## Acceptance criteria

All criteria come from the ticket, in its words.

- **AC1.** `GET /tasks` answers 200 with the tasks newest first: by `created_at` descending, and tasks created at the same time in the order they were created, latest first.
- **AC2.** `?status=open` gives only the tasks with `done: false`, and `?status=done` only those with `done: true`. `?status=all` or no `status` gives every task. Any other value is a 422.
- **AC3.** `POST /tasks` with a valid body answers 201 with the new task: the title trimmed, `notes` `""` and `due` `null` when not sent, `done` `false`, `done_at` `null`, a new UUID `id`, and `created_at` now, sent with six fractional digits and `Z`.
- **AC4.** `POST /tasks` answers 422 for a missing title, a title empty after trimming or longer than 200 characters, notes longer than 2,000 characters, a `due` that is not `YYYY-MM-DD`, or any other field, `id`, `created_at` and `done_at` included.
- **AC5.** `tests/test_tasks.py` covers AC1 to AC4 in place of its 501 checks, seeding tasks through the store. Ruff and pytest pass in CI.

## Scope

- **In:** `app/routes/tasks.py` and `tests/test_tasks.py`.
- **Out (from the ticket):** one task's own endpoints (`/tasks/{id}`), the summary, and any change to `docs/contracts/api.md`, `app/models.py` or `app/store.py`.

## Derived requirements

- **D1 (derived).** The endpoints ship behind the feature flag `TASKS_LIST_CREATE_ENABLED`, off by default. While it is off they keep answering `501 {"detail": "Not implemented"}`, as the contract's "Current status" table says today; input is still validated first, so the 422s of AC2 and AC4 hold either way.
