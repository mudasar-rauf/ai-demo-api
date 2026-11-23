# Spec: #9 The due date accepts only YYYY-MM-DD

**Ticket:** #9   **Plan:** [docs/plans/9-due-date-accepts-only.md](../plans/9-due-date-accepts-only.md)

## User story

As a client of the Tasks API, I want a task's `due` to be accepted only as a `YYYY-MM-DD` date or `null`, as `docs/contracts/api.md` says, so that a number or any other shape is refused with a validation error instead of being silently read as a Unix time and stored as a different date.

## Outcome

The API refuses a `due` that is not a `YYYY-MM-DD` string, as `docs/contracts/api.md` says. Today `{"due": 1763856000}`, or the same number as a string, is read as a Unix time and stored as 2025-11-23.

## Acceptance criteria

AC1 to AC3 come from the ticket, in its words. AC4 is derived.

- **AC1.** `TaskCreate` and `TaskUpdate` refuse a `due` that is a number, a numeric string such as `"1763856000"`, or any string not shaped `YYYY-MM-DD`, with a validation error.
- **AC2.** A real `YYYY-MM-DD` date is accepted as before, an impossible one such as `"2026-02-30"` is refused, and `null` is accepted. In `TaskUpdate`, `due: null` still clears the date.
- **AC3.** `tests/test_models.py` covers AC1 and AC2 for both models. Ruff and pytest pass in CI.
- **AC4** (derived). The OpenAPI schema of `due` still shows a string of format `date`, or `null`; the `Task` response model and the store are unchanged.

## Out of scope

Any change to `docs/contracts/api.md`, the routes, the store or their tests. No feature flag: merging it is the fix.
