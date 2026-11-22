# Tasks API

A small Python 3.11 and FastAPI service behind the Tasks web app. Its contract, every endpoint, field and error, is in [docs/contracts/api.md](docs/contracts/api.md).

Tasks are kept in memory, so they are lost when the server stops.

## Install

You need Python 3.11.

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Run

```bash
uvicorn app.main:app --reload
```

The API listens on `http://localhost:8000`; its interactive documentation is at `http://localhost:8000/docs`. Run a single worker: the in-memory store is not shared between processes.

CORS allows the web app's development address, `http://localhost:3000`.

## Test

```bash
pytest
ruff check .
ruff format --check .
```

CI (`.github/workflows/ci.yml`) runs the same three commands on every pull request into `main`.

## Layout

| Path | What it holds |
|---|---|
| `app/main.py` | The app, CORS, `GET /health`, and the routers |
| `app/models.py` | The Pydantic models of the contract |
| `app/store.py` | The in-memory `TaskStore`, injected with `Depends(get_store)` |
| `app/routes/tasks.py` | `GET /tasks`, `POST /tasks` |
| `app/routes/task.py` | `GET`, `PATCH`, `DELETE /tasks/{id}` |
| `app/routes/summary.py` | `GET /tasks/summary` |
| `tests/` | The tests; `conftest.py` gives each test a fresh, empty store |
