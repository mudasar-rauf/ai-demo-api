"""The Tasks API: the app, CORS, GET /health and the routers."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.models import Health
from app.routes import summary, task, tasks

WEB_APP_ORIGINS = ["http://localhost:3000"]

app = FastAPI(title="Tasks API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=WEB_APP_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=Health, tags=["health"])
def health() -> Health:
    return Health(status="ok")


# summary before task, so /tasks/summary is never matched as /tasks/{task_id}.
app.include_router(summary.router)
app.include_router(tasks.router)
app.include_router(task.router)
