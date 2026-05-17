from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Response

from .auth import require_api_key
from .database import projects, tasks
from .models import Project, Task, TaskCreate, TaskStatus, TaskUpdate

app = FastAPI(title="Project Management API")

DEFAULT_PAGE = 1
DEFAULT_PAGE_SIZE = 20


@app.get("/projects", response_model=List[Project])
async def list_projects():
    return projects


@app.get("/tasks", response_model=List[Task])
async def list_tasks(
    status: Optional[TaskStatus] = None,
    priority: Optional[int] = None,
    assigned_to: Optional[str] = None,
    page: int = Query(default=DEFAULT_PAGE, ge=1),
    page_size: int = Query(default=DEFAULT_PAGE_SIZE, ge=1),
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
    task = find_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.post("/tasks", response_model=Task, status_code=201)
async def create_task(task_data: TaskCreate, _: str = Depends(require_api_key)):
    if not project_exists(task_data.project_id):
        raise HTTPException(status_code=404, detail="Project not found")

    task = Task(id=get_next_task_id(), **task_data.model_dump())
    tasks.append(task)
    return task


@app.put("/tasks/{task_id}", response_model=Task)
async def update_task(task_id: int, task_data: TaskUpdate, _: str = Depends(require_api_key)):
    task = find_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    updates = task_data.model_dump(exclude_unset=True)
    updated_task = task.model_copy(update=updates)
    replace_task(task_id, updated_task)
    return updated_task


@app.delete("/tasks/{task_id}", status_code=204)
async def delete_task(task_id: int, _: str = Depends(require_api_key)):
    task = find_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    tasks.remove(task)
    return Response(status_code=204)


def find_task(task_id: int) -> Optional[Task]:
    for task in tasks:
        if task.id == task_id:
            return task
    return None


def project_exists(project_id: int) -> bool:
    return any(project.id == project_id for project in projects)


def get_next_task_id() -> int:
    if not tasks:
        return 1
    return max(task.id for task in tasks) + 1


def replace_task(task_id: int, updated_task: Task) -> None:
    for index, task in enumerate(tasks):
        if task.id == task_id:
            tasks[index] = updated_task
            return
