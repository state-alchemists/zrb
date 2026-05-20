from fastapi import FastAPI, HTTPException, Query
from typing import List, Optional
from .models import Task, TaskCreate, TaskUpdate, Project, TaskStatus
from .database import tasks, projects
from .auth import require_api_key

app = FastAPI(title="Project Management API")


def _find_task(task_id: int) -> Optional[Task]:
    for task in tasks:
        if task.id == task_id:
            return task
    return None


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
    end = start + page_size
    return filtered[start:end]


@app.get("/tasks/{task_id}", response_model=Task)
async def get_task(task_id: int):
    task = _find_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.post("/tasks", response_model=Task, status_code=201)
async def create_task(
    payload: TaskCreate,
    username: str = require_api_key,
):
    if not any(p.id == payload.project_id for p in projects):
        raise HTTPException(status_code=404, detail="Project not found")

    new_id = max(t.id for t in tasks) + 1
    task = Task(
        id=new_id,
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
    username: str = require_api_key,
):
    task = _find_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(task, field, value)
    return task


@app.delete("/tasks/{task_id}", status_code=204)
async def delete_task(
    task_id: int,
    username: str = require_api_key,
):
    task = _find_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    tasks.remove(task)
    return None
