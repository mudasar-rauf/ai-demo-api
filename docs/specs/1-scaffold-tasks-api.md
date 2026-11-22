# Spec: #1 Scaffold the Tasks API: FastAPI, its contract, and every endpoint wired

**Ticket:** #1   **Plan:** [docs/plans/1-scaffold-tasks-api.md](../plans/1-scaffold-tasks-api.md)

## User story

As a developer building the Tasks web app and the API's later issues, I want a Python 3.11 FastAPI service whose contract declares every endpoint, with each endpoint wired and answering `501 Not Implemented`, so that the web app can be built against a fixed contract and each later issue only has to fill in its own route module and tests.

## Outcome

The Tasks API exists as a Python 3.11 and FastAPI service. Its contract, `docs/contracts/api.md`, declares every endpoint the web app will call. Every endpoint is wired and answers `501 Not Implemented` until an issue builds it. `GET /health` already answers. CI runs on every pull request.

## Acceptance criteria

All criteria come from the ticket, in its words.

- **AC1.** `docs/contracts/api.md` declares the seven endpoints below, each with its method, path, request, response and errors. Each body is shown as the Pydantic model and the TypeScript type side by side. It also declares the task's fields:
  - `id`: a UUID string made by the API.
  - `title`: 1 to 200 characters, trimmed, required.
  - `notes`: up to 2,000 characters.
  - `due`: a `YYYY-MM-DD` date, or null.
  - `done`: a boolean.
  - `created_at`: a UTC date-time.
  - `done_at`: set when `done` becomes true and cleared when it becomes false.
- **AC2.** The seven endpoints:
  - `GET /health`;
  - `GET /tasks?status=all|open|done`, newest first;
  - `POST /tasks`, answering 201;
  - `GET /tasks/{id}` and `PATCH /tasks/{id}`;
  - `DELETE /tasks/{id}`, answering 204;
  - `GET /tasks/summary` (`total`, `open`, `done`).

  Errors are `{"detail": "..."}`: 404 for an unknown task, 422 for an invalid request.
- **AC3.** `GET /health` answers 200 with `{"status": "ok"}`. Every other endpoint answers 501 with `{"detail": "Not implemented"}`. `/tasks/summary` is routed before `/tasks/{id}`.
- **AC4.** The Pydantic models in `app/models.py` match the contract field for field. The in-memory store in `app/store.py` keeps tasks behind one small interface, with its own tests, so each test starts empty.
- **AC5.** CORS allows `http://localhost:3000`, the web app's development address.
- **AC6.** `pyproject.toml` pins Python 3.11 and every dependency the API's three issues need: FastAPI, Pydantic, Uvicorn, and for development pytest, httpx and Ruff. No later issue adds one.
- **AC7.** `.github/workflows/ci.yml` runs `ruff check`, `ruff format --check` and `pytest` on every pull request into `main`, and replaces `spike-ci.yml`.
- **AC8.** Tests cover `GET /health`, and that each of the six other endpoints answers 501. `README.md` says how to install, run (`uvicorn app.main:app`) and test.

## Files

The scaffold creates these files. The three later demo issues change only their own route module and its test file:

- `app/main.py`: the app, CORS, and the routers included;
- `app/models.py`, `app/store.py`;
- `app/routes/tasks.py`: list and create;
- `app/routes/task.py`: get, patch and delete;
- `app/routes/summary.py`;
- `tests/conftest.py`, `tests/test_health.py`, `tests/test_store.py`;
- `tests/test_tasks.py`, `tests/test_task.py`, `tests/test_summary.py`: each holding the 501 check for now;
- `docs/contracts/api.md`, `pyproject.toml`, `README.md`, `.github/workflows/ci.yml`.

## Out of scope

Building any endpoint but `/health`. A database. Sign-in.
