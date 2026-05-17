from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query

from .auth import require_api_key
from .database import projects, tasks
from .models import Project, Task, TaskCreate, TaskStatus, TaskUpdate

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
    page_size: int = Query(default=20, ge=1),
):
    filtered_tasks = [
        task
        for task in tasks
        if (status is None or task.status == status)
        and (priority is None or task.priority == priority)
        and (assigned_to is None or task.assigned_to == assigned_to)
    ]
    start_index = (page - 1) * page_size
    end_index = start_index + page_size
    return filtered_tasks[start_index:end_index]


@app.get("/tasks/{task_id}", response_model=Task)
async def get_task(task_id: int):
    return find_task(task_id)


@app.post("/tasks", response_model=Task)
async def create_task(task_data: TaskCreate, _: str = Depends(require_api_key)):
    ensure_project_exists(task_data.project_id)
    task = Task(id=get_next_task_id(), **task_data.model_dump())
    tasks.append(task)
    return task


@app.put("/tasks/{task_id}", response_model=Task)
async def update_task(
    task_id: int,
    task_update: TaskUpdate,
    _: str = Depends(require_api_key),
):
    task = find_task(task_id)
    update_data = task_update.model_dump(exclude_unset=True)
    updated_task = task.model_copy(update=update_data)
    replace_task(task_id, updated_task)
    return updated_task


@app.delete("/tasks/{task_id}")
async def delete_task(task_id: int, _: str = Depends(require_api_key)):
    task = find_task(task_id)
    tasks.remove(task)
    return {"detail": "Task deleted"}


def find_task(task_id: int) -> Task:
    for task in tasks:
        if task.id == task_id:
            return task
    raise HTTPException(status_code=404, detail="Task not found")


def ensure_project_exists(project_id: int) -> None:
    for project in projects:
        if project.id == project_id:
            return
    raise HTTPException(status_code=404, detail="Project not found")


def get_next_task_id() -> int:
    if not tasks:
        return 1
    return max(task.id for task in tasks) + 1


def replace_task(task_id: int, updated_task: Task) -> None:
    for index, task in enumerate(tasks):
        if task.id == task_id:
            tasks[index] = updated_task
            return
