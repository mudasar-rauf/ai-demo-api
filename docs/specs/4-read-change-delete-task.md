# Spec: #4 Read, change and delete one task

**Ticket:** #4   **Plan:** [docs/plans/4-read-change-delete-task.md](../plans/4-read-change-delete-task.md)   **Contract:** [docs/contracts/api.md](../contracts/api.md)

## User story

As a person using the Tasks web app, I want to open one task, change any of its fields (including marking it done or not done), and delete it, so that I can keep my tasks up to date.

## Outcome

A person can read one task through the API, change any of its fields (marking it done or not done), and delete it.

## Acceptance criteria

AC1 to AC5 come from the ticket, in its words. There is no feature flag: until this issue is merged, the scaffold's 501 is the off state, and merging it is the release.

- **AC1.** `GET /tasks/{id}` answers 200 with the task. An unknown id is a 404 with `{"detail": "Task not found"}`, and an id that is not a UUID is a 422.
- **AC2.** `PATCH /tasks/{id}` changes only the fields sent and answers 200 with the task after the change. `{}` changes nothing, and `due: null` clears the date. A `null` `title`, `notes` or `done`, a field breaking its rule, or any other field (`id`, `created_at` and `done_at` included) is a 422. An unknown id is a 404. (Since #9, `due` takes only a `YYYY-MM-DD` string or `null`: a number such as `1763856000` or a numeric string such as `"1763856000"` breaks its rule and is a 422.)
- **AC3.** `done` going from false to true sets `done_at` to now. Going from true to false sets it to `null`. Sending `done` with its current value leaves `done_at` as it was.
- **AC4.** `DELETE /tasks/{id}` answers 204 with no body, and the task is gone: a later `GET /tasks/{id}` is a 404. An unknown id is a 404, and an id that is not a UUID is a 422.
- **AC5.** `tests/test_task.py` covers AC1 to AC4 in place of its 501 checks, seeding tasks through the store. Ruff and pytest pass in CI.

## Out of scope

Listing and adding tasks, the summary, and any change to `docs/contracts/api.md`, `app/models.py` or `app/store.py`.
