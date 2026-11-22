"""GET /tasks and POST /tasks: list and create."""

from fastapi import APIRouter, Depends, HTTPException

from app.models import Task, TaskCreate, TaskStatus
from app.store import TaskStore, get_store

router = APIRouter(tags=["tasks"])


@router.get("/tasks", response_model=list[Task])
def list_tasks(
    status: TaskStatus = TaskStatus.all, store: TaskStore = Depends(get_store)
) -> list[Task]:
    raise HTTPException(status_code=501, detail="Not implemented")


@router.post("/tasks", response_model=Task, status_code=201)
def create_task(body: TaskCreate, store: TaskStore = Depends(get_store)) -> Task:
    raise HTTPException(status_code=501, detail="Not implemented")
