from fastapi import Depends, FastAPI, HTTPException, Query
from typing import List
from .models import Project, Task, TaskCreate, TaskStatus, TaskUpdate
from .database import projects, tasks
from .auth import require_api_key

app = FastAPI(title="Project Management API")


@app.get("/projects", response_model=List[Project])
async def list_projects():
    return projects


@app.get("/tasks", response_model=List[Task])
async def list_tasks(
    status: TaskStatus | None = None,
    priority: int | None = None,
    assigned_to: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1),
):
    filtered_tasks = [
        task
        for task in tasks
        if (status is None or task.status == status)
        and (priority is None or task.priority == priority)
        and (assigned_to is None or task.assigned_to == assigned_to)
    ]
    start = (page - 1) * page_size
    end = start + page_size
    return filtered_tasks[start:end]


@app.get("/tasks/{task_id}", response_model=Task)
async def get_task(task_id: int):
    task = _find_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.post("/tasks", response_model=Task)
async def create_task(task: TaskCreate, _: str = Depends(require_api_key)):
    if _find_project(task.project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")

    new_task = Task(id=_next_task_id(), **task.model_dump())
    tasks.append(new_task)
    return new_task


@app.put("/tasks/{task_id}", response_model=Task)
async def update_task(task_id: int, task_update: TaskUpdate, _: str = Depends(require_api_key)):
    task = _find_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    updates = task_update.model_dump(exclude_unset=True)
    updated_task = task.model_copy(update=updates)
    index = tasks.index(task)
    tasks[index] = updated_task
    return updated_task


@app.delete("/tasks/{task_id}")
async def delete_task(task_id: int, _: str = Depends(require_api_key)):
    task = _find_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    tasks.remove(task)
    return {"detail": "Task deleted"}


def _find_task(task_id: int) -> Task | None:
    for task in tasks:
        if task.id == task_id:
            return task
    return None


def _find_project(project_id: int) -> Project | None:
    for project in projects:
        if project.id == project_id:
            return project
    return None


def _next_task_id() -> int:
    if not tasks:
        return 1
    return max(task.id for task in tasks) + 1
