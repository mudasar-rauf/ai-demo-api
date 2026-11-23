"""GET, PATCH and DELETE /tasks/{task_id}: one task."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response

from app.models import Task, TaskUpdate
from app.store import TaskStore, get_store

TASK_NOT_FOUND = "Task not found"

router = APIRouter(tags=["tasks"])


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail=TASK_NOT_FOUND)


@router.get("/tasks/{task_id}", response_model=Task)
def get_task(task_id: UUID, store: TaskStore = Depends(get_store)) -> Task:
    task = store.get(task_id)
    if task is None:
        raise _not_found()
    return task


@router.patch("/tasks/{task_id}", response_model=Task)
def update_task(task_id: UUID, body: TaskUpdate, store: TaskStore = Depends(get_store)) -> Task:
    """Only the fields sent change; the store sets or clears done_at when done changes."""
    task = store.update(task_id, body)
    if task is None:
        raise _not_found()
    return task


@router.delete("/tasks/{task_id}", status_code=204, response_class=Response)
def delete_task(task_id: UUID, store: TaskStore = Depends(get_store)) -> Response:
    if not store.delete(task_id):
        raise _not_found()
    return Response(status_code=204)
