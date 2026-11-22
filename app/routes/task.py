"""GET, PATCH and DELETE /tasks/{task_id}: one task."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response

from app.models import Task, TaskUpdate
from app.store import TaskStore, get_store

router = APIRouter(tags=["tasks"])


@router.get("/tasks/{task_id}", response_model=Task)
def get_task(task_id: UUID, store: TaskStore = Depends(get_store)) -> Task:
    raise HTTPException(status_code=501, detail="Not implemented")


@router.patch("/tasks/{task_id}", response_model=Task)
def update_task(task_id: UUID, body: TaskUpdate, store: TaskStore = Depends(get_store)) -> Task:
    raise HTTPException(status_code=501, detail="Not implemented")


@router.delete("/tasks/{task_id}", status_code=204, response_class=Response)
def delete_task(task_id: UUID, store: TaskStore = Depends(get_store)) -> None:
    raise HTTPException(status_code=501, detail="Not implemented")
