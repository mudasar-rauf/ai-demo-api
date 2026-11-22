# Technical Plan: #1 Scaffold the Tasks API: FastAPI, its contract, and every endpoint wired

**Ticket:** #1   **Spec:** [docs/specs/1-scaffold-tasks-api.md](../specs/1-scaffold-tasks-api.md)   **Status:** Draft

## 1. Summary

We create the Tasks API from an empty repository: a Python 3.11 FastAPI app with its written contract (`docs/contracts/api.md`), Pydantic models, an in-memory store behind a small interface, and three route modules that wire all six task endpoints to `501 Not Implemented`. Only `GET /health` really answers. CI (Ruff and pytest) replaces the spike workflow. The layout gives each of the three later issues one route module and one test file to change, so they can run in parallel without touching shared files.

## 2. Requirements

### User story

See the [spec](../specs/1-scaffold-tasks-api.md#user-story).

### Acceptance criteria

| ID | Criterion (short) | Source |
|---|---|---|
| AC1 | `docs/contracts/api.md` declares the seven endpoints (method, path, request, response, errors), each body as Pydantic and TypeScript side by side, and the task's fields | ticket |
| AC2 | The seven endpoints, with 201 on create, 204 on delete, newest-first list, `{"detail": ...}` errors: 404 unknown task, 422 invalid request | ticket |
| AC3 | `/health` → 200 `{"status": "ok"}`; every other endpoint → 501 `{"detail": "Not implemented"}`; `/tasks/summary` routed before `/tasks/{id}` | ticket |
| AC4 | Models in `app/models.py` match the contract field for field; store in `app/store.py` behind one small interface, with its own tests; each test starts empty | ticket |
| AC5 | CORS allows `http://localhost:3000` | ticket |
| AC6 | `pyproject.toml` pins Python 3.11, FastAPI, Pydantic, Uvicorn; dev: pytest, httpx, Ruff | ticket |
| AC7 | `.github/workflows/ci.yml` runs `ruff check`, `ruff format --check`, `pytest` on PRs into `main`; `spike-ci.yml` removed | ticket |
| AC8 | Tests for `/health` and the 501 of each of the six other endpoints; `README.md` covers install, run, test | ticket |

### Non-functional requirements

- The contract is the source of truth for the web app and the three later issues; the models must not drift from it (AC4).
- Later issues must not need to edit `app/main.py`, `app/models.py`, `app/store.py`, `pyproject.toml` or CI. Everything they share is decided here.

### Out of scope

Building any endpoint but `/health`; a database; sign-in; deployment.

### Assumptions

- **A1.** `notes` is a non-null string defaulting to `""` (the ticket gives only its maximum length). The TypeScript type is `string`.
- **A2.** `title` is trimmed before its length is checked; a title that is empty after trimming is a 422. `notes` is not trimmed.
- **A3.** `PATCH /tasks/{id}` takes any subset of `title`, `notes`, `due`, `done`; `due: null` clears the date. An empty body is valid and changes nothing. Unknown fields are rejected with 422 (`extra="forbid"`), as are `id`, `created_at` and `done_at`, which the client cannot set.
- **A4.** `GET /tasks` with no `status` means `all`; any other value is a 422. "Newest first" means by `created_at` descending, ties broken by insertion order (latest first).
- **A5.** `created_at` and `done_at` are serialised as ISO 8601 UTC with a `Z` suffix, e.g. `2026-11-22T09:30:00Z`.
- **A6.** The 404 body is `{"detail": "Task not found"}`. 422 uses FastAPI's default validation body, whose `detail` is a list of error objects; the contract says so rather than forcing a string (see Q1).
- **A7.** "Pins" means exact `==` versions in `pyproject.toml`, chosen at implementation time as the latest stable releases that support Python 3.11. No lock file.

## 3. Current state

The repository holds only `.factory/workflow.yaml` (the factory's pipeline) and `.github/workflows/spike-ci.yml`, a placeholder job that echoes on every pull request into `main`. There is no application code, no `CLAUDE.md`, no README and no existing pattern to follow; this plan sets the patterns.

## 4. Proposed design

### Overview

```
HTTP ──> app.main:app (FastAPI, CORSMiddleware)
           ├─ GET /health                       (in main.py)
           ├─ routes/summary.py  GET /tasks/summary     ─┐ included first
           ├─ routes/tasks.py    GET/POST /tasks         │
           └─ routes/task.py     GET/PATCH/DELETE /tasks/{id}
                                     │  Depends(get_store)
                                     v
                         store.py: TaskStore (in-memory dict)
```

Route handlers take the store through FastAPI's dependency injection (`Depends(get_store)`), so tests replace it with a fresh instance per test via `app.dependency_overrides`.

### Changes by component

| File | Change | New / modified |
|---|---|---|
| `pyproject.toml` | Project metadata, `requires-python = ">=3.11,<3.12"`, pinned deps, `[project.optional-dependencies] dev`, Ruff and pytest config, setuptools packaging of `app` | New |
| `app/__init__.py`, `app/routes/__init__.py` | Empty package markers | New |
| `app/main.py` | `app = FastAPI(title="Tasks API")`, CORS, `GET /health`, include routers in order: summary, tasks, task | New |
| `app/models.py` | `TaskCreate`, `TaskUpdate`, `Task`, `TaskStatus`, `Summary`, `Health` | New |
| `app/store.py` | `TaskStore` and `get_store()` | New |
| `app/routes/tasks.py` | `router`: `GET /tasks`, `POST /tasks` → 501 | New |
| `app/routes/task.py` | `router`: `GET/PATCH/DELETE /tasks/{task_id}` → 501 | New |
| `app/routes/summary.py` | `router`: `GET /tasks/summary` → 501 | New |
| `tests/conftest.py` | `store` fixture (fresh `TaskStore`), `client` fixture (`TestClient` with the override) | New |
| `tests/test_health.py`, `tests/test_store.py`, `tests/test_tasks.py`, `tests/test_task.py`, `tests/test_summary.py` | Tests (section 7) | New |
| `docs/contracts/api.md` | The contract | New |
| `README.md` | Install, run, test | New |
| `.github/workflows/ci.yml` | Ruff and pytest on PRs into `main` | New |
| `.github/workflows/spike-ci.yml` | Deleted | Removed |

### Data model

```python
# app/models.py
class TaskStatus(str, Enum):
    all = "all"; open = "open"; done = "done"

class TaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    notes: Annotated[str, StringConstraints(max_length=2000)] = ""
    due: date | None = None

class TaskUpdate(BaseModel):          # every field optional; only sent fields change
    model_config = ConfigDict(extra="forbid")
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)] | None = None
    notes: Annotated[str, StringConstraints(max_length=2000)] | None = None
    due: date | None = None
    done: bool | None = None

class Task(BaseModel):
    id: UUID
    title: str
    notes: str
    due: date | None
    done: bool
    created_at: datetime              # timezone-aware UTC
    done_at: datetime | None

class Summary(BaseModel):
    total: int; open: int; done: int

class Health(BaseModel):
    status: Literal["ok"]
```

`TaskUpdate` callers use `model_dump(exclude_unset=True)` so that `due: null` (clear) differs from `due` absent (keep). `title: null` and `done: null` in a PATCH are 422 — the issue implementing PATCH validates that; the contract states it now.

```python
# app/store.py — the whole interface the route issues may use
class TaskStore:
    def list(self, status: TaskStatus = TaskStatus.all) -> list[Task]  # newest first
    def add(self, data: TaskCreate) -> Task          # makes id, created_at; done=False, done_at=None
    def get(self, task_id: UUID) -> Task | None
    def update(self, task_id: UUID, changes: TaskUpdate) -> Task | None  # sets/clears done_at
    def delete(self, task_id: UUID) -> bool
    def summary(self) -> Summary

_store = TaskStore()
def get_store() -> TaskStore: return _store
```

The store is implemented fully here (not stubbed), because AC4 requires its own tests and the `done_at` rule belongs in one place. The route issues then only translate HTTP to store calls. `TaskStore.__init__` takes an optional `clock: Callable[[], datetime]` (default `lambda: datetime.now(UTC)`) so ordering and `done_at` tests are deterministic.

### APIs and contracts

`docs/contracts/api.md` contains, for each endpoint, a section with method and path, query/path parameters, request body, success status and body, and errors; bodies are shown as a two-column table or two adjacent code blocks: Pydantic on the left, TypeScript on the right. TypeScript types:

```ts
type Task = { id: string; title: string; notes: string; due: string | null;
              done: boolean; created_at: string; done_at: string | null };
type TaskCreate = { title: string; notes?: string; due?: string | null };
type TaskUpdate = Partial<{ title: string; notes: string; due: string | null; done: boolean }>;
type TaskStatus = "all" | "open" | "done";
type Summary = { total: number; open: number; done: number };
type Health = { status: "ok" };
type ErrorBody = { detail: string };          // 404, 501
```

| Method | Path | Request | Success | Errors |
|---|---|---|---|---|
| GET | `/health` | — | 200 `Health` | — |
| GET | `/tasks?status=all\|open\|done` | query `status`, default `all` | 200 `Task[]`, newest first | 422 bad `status` |
| POST | `/tasks` | `TaskCreate` | 201 `Task` | 422 |
| GET | `/tasks/summary` | — | 200 `Summary` | — |
| GET | `/tasks/{id}` | path `id` (UUID) | 200 `Task` | 404, 422 non-UUID id |
| PATCH | `/tasks/{id}` | `TaskUpdate` | 200 `Task` | 404, 422 |
| DELETE | `/tasks/{id}` | — | 204, no body | 404, 422 non-UUID id |

The contract also has a "Task fields" table with the AC1 rules (and A1–A5), a "Current status" note that every endpoint except `/health` answers `501 {"detail": "Not implemented"}` until its issue lands, and the CORS origin.

Route stubs declare their final signatures, status codes and `response_model` now, so the OpenAPI schema at `/docs` already matches the contract, and raise `HTTPException(501, "Not implemented")` in the body. Example:

```python
@router.post("/tasks", response_model=Task, status_code=201)
def create_task(body: TaskCreate, store: TaskStore = Depends(get_store)) -> Task:
    raise HTTPException(status_code=501, detail="Not implemented")
```

Consequence: a stub with a body or a UUID path parameter validates its input first, so the 501 tests must send a valid body and a valid UUID (an invalid one would get 422). That is the behaviour the later issues keep.

### Error handling and edge cases

- `/tasks/summary` vs `/tasks/{id}`: `summary.router` is included before `task.router`; additionally `task_id` is typed `UUID`, so `summary` could never match it as an id. A test asserts `GET /tasks/summary` hits the summary handler (501 with the summary stub, not a 422 from UUID parsing).
- `done_at`: set to now when `done` goes false→true; cleared to `None` when true→false; unchanged when `done` is sent with its current value.

### Security, performance, observability

CORS: `CORSMiddleware(allow_origins=["http://localhost:3000"], allow_methods=["*"], allow_headers=["*"])`, no credentials (no sign-in). No other origin is allowed. In-memory store is single-process and not thread-safe beyond the GIL; acceptable for a demo (see risks).

## 5. Key decisions

| Decision | Choice | Rationale | Alternatives rejected |
|---|---|---|---|
| Store access | `Depends(get_store)` + `dependency_overrides` in tests | Each test starts empty without global resets; idiomatic FastAPI | Module-global with a `clear()` fixture: works, but leaks state if a test forgets the fixture |
| Store completeness | Fully implemented with tests now | AC4 wants store tests; keeps `done_at` logic in one place, so the three route issues stay independent | Stub store filled by the route issues: they would all edit `store.py` and collide |
| Stub signatures | Final signatures and `response_model` now, body raises 501 | Contract visible in OpenAPI; later issues change only the body | Bare `def f(): raise ...`: later issues would redesign signatures, risking drift |
| Router split | `tasks.py` (collection), `task.py` (item), `summary.py` | Given by the ticket; one module per later issue | — |
| 422 body | FastAPI default (`detail` is a list) | Matches framework behaviour; no custom handler to maintain | Custom handler flattening to a string — see Q1 |
| Packaging | setuptools, `pip install -e ".[dev]"` | Standard, no extra tool | Poetry/uv: extra tool for CI and README |

No ADR: this is the first code in the repository and every choice is reversible; the contract itself is the significant artefact and is reviewed with this plan.

## 6. Implementation tasks

### T1. Project, CI and README (S)
- Goal: an installable empty package with working lint and test tooling in CI.
- Changes: `pyproject.toml`, `app/__init__.py`, `app/routes/__init__.py`, `README.md`, `.github/workflows/ci.yml`; delete `.github/workflows/spike-ci.yml`.
- Details: `requires-python = ">=3.11,<3.12"`; dependencies `fastapi==…`, `pydantic==…`, `uvicorn[standard]==…`; dev extras `pytest==…`, `httpx==…`, `ruff==…` (A7). `[tool.ruff] target-version = "py311"`, `line-length = 100`, lint select `E,F,I,UP,B`. `[tool.pytest.ini_options] testpaths = ["tests"]`. CI: one job `test` on `pull_request` into `main`, `ubuntu-latest`, `actions/checkout@v4`, `actions/setup-python@v5` with `python-version: "3.11"` and pip cache, `pip install -e ".[dev]"`, then `ruff check .`, `ruff format --check .`, `pytest`. README: install (`python3.11 -m venv .venv`, `pip install -e ".[dev]"`), run (`uvicorn app.main:app --reload`, port 8000, docs at `/docs`), test (`pytest`, `ruff check .`, `ruff format --check .`), and a link to the contract.
- Done when: AC6, AC7 and the README half of AC8 hold.
- Tests: CI run on the pull request itself.
- Depends on: none.

### T2. Contract and models (M)
- Goal: the contract written, and models that match it.
- Changes: `docs/contracts/api.md`, `app/models.py`.
- Details: as section 4. Write the contract first, then the models from it.
- Done when: AC1, AC2 (as declared), and the models half of AC4.
- Tests: in `tests/test_store.py` (T3) — validation cases on `TaskCreate`/`TaskUpdate`: title trimmed, empty/whitespace and 201-char titles rejected, 2001-char notes rejected, bad date rejected, extra field rejected.
- Depends on: T1.

### T3. In-memory store (S)
- Goal: `TaskStore` and `get_store` with tests.
- Changes: `app/store.py`, `tests/test_store.py`.
- Done when: the store half of AC4.
- Tests: add assigns UUID, `created_at`, `done=False`; list newest first and filtered by status; get/update/delete of unknown id return `None`/`False`; update sets `done_at` on done→true and clears it on →false, and leaves it on a no-op; `due: None` sent clears the date, absent keeps it; summary counts; two fresh instances share nothing.
- Depends on: T2.

### T4. App, routers and 501 tests (S)
- Goal: every endpoint wired.
- Changes: `app/main.py`, `app/routes/tasks.py`, `app/routes/task.py`, `app/routes/summary.py`, `tests/conftest.py`, `tests/test_health.py`, `tests/test_tasks.py`, `tests/test_task.py`, `tests/test_summary.py`.
- Details: section 4. `conftest.py` fixtures: `store` → `TaskStore()`; `client` → sets `app.dependency_overrides[get_store] = lambda: store`, yields `TestClient(app)`, then clears the overrides.
- Done when: AC3, AC5, the tests half of AC8.
- Tests: `/health` 200 `{"status": "ok"}`; CORS preflight from `http://localhost:3000` returns `access-control-allow-origin: http://localhost:3000` and one from another origin does not; `test_tasks.py`: `GET /tasks` and `POST /tasks` (valid body) → 501 body; `test_task.py`: GET/PATCH (valid body)/DELETE on a random UUID → 501; `test_summary.py`: `GET /tasks/summary` → 501 `{"detail": "Not implemented"}`.
- Depends on: T3.

### Sequence

T1 → T2 → T3 → T4, one developer, one pull request (this one). Total: about 1.5 days (S + M + S + S). T1 could run alongside T2 but the whole is small enough that parallelism is not worth it.

## 7. Test strategy

| AC | Tasks | Test type | What the test verifies |
|---|---|---|---|
| AC1 | T2 | Review | Contract has seven endpoint sections, field table, Pydantic and TS side by side |
| AC2 | T2, T4 | Review + unit | Contract lists the codes; stubs declare 201/204 status codes; OpenAPI paths match the seven endpoints (`app.openapi()["paths"]` test in `test_health.py`) |
| AC3 | T4 | API (TestClient) | `/health` 200; six 501s; summary path reaches summary stub |
| AC4 | T2, T3 | Unit | Model validation; store behaviour; fresh store per test |
| AC5 | T4 | API | CORS preflight allowed for `localhost:3000`, not for others |
| AC6 | T1 | CI | `pip install -e ".[dev]"` succeeds on 3.11 |
| AC7 | T1 | CI | The workflow runs and passes on this PR; spike workflow gone |
| AC8 | T1, T4 | API + review | Tests above exist; README has install/run/test |

Regression risk: none in code. The factory's `checks` stage reads GitHub checks; removing `spike-ci.yml` in the same PR that adds `ci.yml` keeps a check on every PR.

## 8. Rollout and rollback

**Feature flag.** No runtime flag. The scaffold's "off" state is the 501 stub itself: every task endpoint is wired but answers `501 Not implemented`, so nothing user-facing is switched on. A flag such as `TASKS_API_ENABLED` would only toggle between 501 and 404 and would conflict with AC3. Each later issue that builds an endpoint names its own flag in its own plan (see Q2).

No migrations, no infrastructure, not deployed anywhere. Rollback: revert the merge commit; `spike-ci.yml` returns with it.

## 9. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Contract and models drift | Medium | Web app breaks | Models written from the contract in T2; OpenAPI path test; reviewer checks field for field |
| A later issue needs a dependency not pinned (AC6 says none may be added) | Low | AC6 broken later | httpx covers TestClient; dates and UUIDs are stdlib; `uvicorn[standard]` covers reload |
| Removing spike CI leaves the factory's checks stage with no check if `ci.yml` is malformed | Low | Checks stage times out | Both changes in one PR; the PR's own CI run proves `ci.yml` works |
| In-memory store not shared across workers | Low | Data split if run with `--workers > 1` | README says run a single worker |

## 10. Technical debt

Taken on knowingly: in-memory storage (architecture debt; follow-up when a database is in scope). No lock file (dependency debt; exact pins mitigate).

## 11. Open questions

| # | Question | Who can answer | Blocks | Assumption made |
|---|---|---|---|---|
| Q1 | Must 422 bodies have a string `detail`, as "Errors are `{"detail": "..."}`" could be read, or is FastAPI's list-valued `detail` acceptable? | Product owner / plan gate | No | FastAPI default; contract documents it (A6). A custom handler can be added in `main.py` if a string is required |
| Q2 | Is the 501 stub an acceptable "off by default" in place of a feature flag for this scaffold? | Plan gate | No | Yes (section 8) |
| Q3 | Are A1–A5 (notes default `""`, PATCH semantics, default status, timestamp format) right for the web app? | Web app owner | No | As stated |

## 12. Follow-ups

- A database-backed `TaskStore` when persistence is in scope.
- Generating the TypeScript types from OpenAPI instead of maintaining them by hand.
