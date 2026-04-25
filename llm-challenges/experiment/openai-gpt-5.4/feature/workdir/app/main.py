from typing import Annotated, List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query

from .auth import require_api_key
from .database import projects, tasks
from .models import Project, Task, TaskCreate, TaskStatus, TaskUpdate

app = FastAPI(title="Project Management API")


def _get_task_or_404(task_id: int) -> Task:
    for task in tasks:
        if task.id == task_id:
            return task
    raise HTTPException(status_code=404, detail="Task not found")


def _project_exists(project_id: int) -> bool:
    return any(project.id == project_id for project in projects)


@app.get("/projects", response_model=List[Project])
async def list_projects():
    return projects


@app.get("/tasks", response_model=List[Task])
async def list_tasks(
    status: Optional[TaskStatus] = None,
    priority: Optional[int] = None,
    assigned_to: Optional[str] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1),
):
    filtered_tasks = tasks

    if status is not None:
        filtered_tasks = [task for task in filtered_tasks if task.status == status]
    if priority is not None:
        filtered_tasks = [task for task in filtered_tasks if task.priority == priority]
    if assigned_to is not None:
        filtered_tasks = [task for task in filtered_tasks if task.assigned_to == assigned_to]

    start = (page - 1) * page_size
    end = start + page_size
    return filtered_tasks[start:end]


@app.get("/tasks/{task_id}", response_model=Task)
async def get_task(task_id: int):
    return _get_task_or_404(task_id)


@app.post("/tasks", response_model=Task)
async def create_task(
    task_create: TaskCreate,
    _: Annotated[str, Depends(require_api_key)],
):
    if not _project_exists(task_create.project_id):
        raise HTTPException(status_code=404, detail="Project not found")

    next_id = max((task.id for task in tasks), default=0) + 1
    task = Task(id=next_id, **task_create.model_dump())
    tasks.append(task)
    return task


@app.put("/tasks/{task_id}", response_model=Task)
async def update_task(
    task_id: int,
    task_update: TaskUpdate,
    _: Annotated[str, Depends(require_api_key)],
):
    task = _get_task_or_404(task_id)
    updates = task_update.model_dump(exclude_unset=True)

    for field, value in updates.items():
        setattr(task, field, value)

    return task


@app.delete("/tasks/{task_id}")
async def delete_task(
    task_id: int,
    _: Annotated[str, Depends(require_api_key)],
):
    task = _get_task_or_404(task_id)
    tasks.remove(task)
    return {"detail": "Task deleted"}
