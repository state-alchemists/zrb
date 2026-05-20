from fastapi import Depends, FastAPI, HTTPException, Query, Response
from typing import List, Optional
from .models import Task, TaskCreate, TaskUpdate, TaskStatus, Project
from .database import tasks, projects
from .auth import require_api_key

app = FastAPI(title="Project Management API")


def _next_task_id() -> int:
    return max((t.id for t in tasks), default=0) + 1


@app.get("/projects", response_model=List[Project])
async def list_projects():
    return projects


@app.get("/tasks", response_model=List[Task])
async def list_tasks(
    status: Optional[TaskStatus] = Query(default=None),
    priority: Optional[int] = Query(default=None),
    assigned_to: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    filtered = tasks
    if status is not None:
        filtered = [t for t in filtered if t.status == status]
    if priority is not None:
        filtered = [t for t in filtered if t.priority == priority]
    if assigned_to is not None:
        filtered = [t for t in filtered if t.assigned_to == assigned_to]

    start = (page - 1) * page_size
    return filtered[start : start + page_size]


@app.get("/tasks/{task_id}", response_model=Task)
async def get_task(task_id: int):
    for task in tasks:
        if task.id == task_id:
            return task
    raise HTTPException(status_code=404, detail="Task not found")


@app.post("/tasks", response_model=Task, status_code=201)
async def create_task(
    payload: TaskCreate,
    _user: str = Depends(require_api_key),
):
    project_exists = any(p.id == payload.project_id for p in projects)
    if not project_exists:
        raise HTTPException(status_code=404, detail="Project not found")
    task = Task(
        id=_next_task_id(),
        title=payload.title,
        status=payload.status,
        priority=payload.priority,
        project_id=payload.project_id,
        assigned_to=payload.assigned_to,
    )
    tasks.append(task)
    return task


@app.put("/tasks/{task_id}", response_model=Task)
async def update_task(
    task_id: int,
    payload: TaskUpdate,
    _user: str = Depends(require_api_key),
):
    for task in tasks:
        if task.id == task_id:
            if payload.title is not None:
                task.title = payload.title
            if payload.status is not None:
                task.status = payload.status
            if payload.priority is not None:
                task.priority = payload.priority
            if payload.assigned_to is not None:
                task.assigned_to = payload.assigned_to
            return task
    raise HTTPException(status_code=404, detail="Task not found")


@app.delete("/tasks/{task_id}", status_code=204)
async def delete_task(
    task_id: int,
    _user: str = Depends(require_api_key),
):
    for i, task in enumerate(tasks):
        if task.id == task_id:
            tasks.pop(i)
            return Response(status_code=204)
    raise HTTPException(status_code=404, detail="Task not found")
