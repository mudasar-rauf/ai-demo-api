"""GET /tasks/summary: counts of the tasks."""

from fastapi import APIRouter, Depends

from app.models import Summary
from app.store import TaskStore, get_store

router = APIRouter(tags=["tasks"])


@router.get("/tasks/summary", response_model=Summary)
def task_summary(store: TaskStore = Depends(get_store)) -> Summary:
    # The store counts under its lock, so total is always open + done.
    return store.summary()
