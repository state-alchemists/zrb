from fastapi import FastAPI, HTTPException, Depends, Query
from typing import List, Optional
from .models import Task, TaskCreate, TaskUpdate, Project, TaskStatus
from .database import tasks, projects
from .auth import require_api_key

app = FastAPI(title="Project Management API")


@app.get("/projects", response_model=List[Project])
async def list_projects():
    return projects


@app.get("/tasks", response_model=List[Task])
async def list_tasks(
    status: Optional[TaskStatus] = None,
    priority: Optional[int] = None,
    assigned_to: Optional[str] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    result = tasks

    if status is not None:
        result = [t for t in result if t.status == status]
    if priority is not None:
        result = [t for t in result if t.priority == priority]
    if assigned_to is not None:
        result = [t for t in result if t.assigned_to == assigned_to]

    start = (page - 1) * page_size
    end = start + page_size
    return result[start:end]


@app.get("/tasks/{task_id}", response_model=Task)
async def get_task(task_id: int):
    for task in tasks:
        if task.id == task_id:
            return task
    raise HTTPException(status_code=404, detail="Task not found")


def _get_next_task_id() -> int:
    if not tasks:
        return 1
    return max(t.id for t in tasks) + 1


@app.post("/tasks", response_model=Task, status_code=201)
async def create_task(task_create: TaskCreate, username: str = Depends(require_api_key)):
    project_exists = any(p.id == task_create.project_id for p in projects)
    if not project_exists:
        raise HTTPException(status_code=404, detail="Project not found")

    new_task = Task(
        id=_get_next_task_id(),
        title=task_create.title,
        status=task_create.status,
        priority=task_create.priority,
        project_id=task_create.project_id,
        assigned_to=task_create.assigned_to,
    )
    tasks.append(new_task)
    return new_task


@app.put("/tasks/{task_id}", response_model=Task)
async def update_task(
    task_id: int,
    task_update: TaskUpdate,
    username: str = Depends(require_api_key),
):
    for task in tasks:
        if task.id == task_id:
            update_data = task_update.model_dump(exclude_unset=True)
            updated_task = task.model_copy(update=update_data)
            tasks[tasks.index(task)] = updated_task
            return updated_task
    raise HTTPException(status_code=404, detail="Task not found")


@app.delete("/tasks/{task_id}", status_code=204)
async def delete_task(task_id: int, username: str = Depends(require_api_key)):
    for i, task in enumerate(tasks):
        if task.id == task_id:
            tasks.pop(i)
            return
    raise HTTPException(status_code=404, detail="Task not found")
