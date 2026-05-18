from fastapi import Depends, FastAPI, HTTPException
from typing import List, Optional
from .models import Task, TaskCreate, TaskUpdate, Project, TaskStatus
from .database import tasks, projects
from .auth import require_api_key

DEFAULT_PAGE = 1
DEFAULT_PAGE_SIZE = 20

app = FastAPI(title="Project Management API")


@app.get("/projects", response_model=List[Project])
async def list_projects():
    return projects


@app.get("/tasks", response_model=List[Task])
async def list_tasks(
    status: Optional[TaskStatus] = None,
    priority: Optional[int] = None,
    assigned_to: Optional[str] = None,
    page: int = DEFAULT_PAGE,
    page_size: int = DEFAULT_PAGE_SIZE,
):
    filtered_tasks = tasks

    if status is not None:
        filtered_tasks = [task for task in filtered_tasks if task.status == status]
    if priority is not None:
        filtered_tasks = [task for task in filtered_tasks if task.priority == priority]
    if assigned_to is not None:
        filtered_tasks = [task for task in filtered_tasks if task.assigned_to == assigned_to]

    start_index = (page - 1) * page_size
    end_index = start_index + page_size
    return filtered_tasks[start_index:end_index]


@app.get("/tasks/{task_id}", response_model=Task)
async def get_task(task_id: int):
    for task in tasks:
        if task.id == task_id:
            return task
    raise HTTPException(status_code=404, detail="Task not found")


@app.post("/tasks", response_model=Task)
async def create_task(
    task_data: TaskCreate,
    _: str = Depends(require_api_key),
):
    if not any(project.id == task_data.project_id for project in projects):
        raise HTTPException(status_code=404, detail="Project not found")

    next_task_id = max((task.id for task in tasks), default=0) + 1
    task = Task(id=next_task_id, **task_data.model_dump())
    tasks.append(task)
    return task


@app.put("/tasks/{task_id}", response_model=Task)
async def update_task(
    task_id: int,
    task_update: TaskUpdate,
    _: str = Depends(require_api_key),
):
    for index, task in enumerate(tasks):
        if task.id != task_id:
            continue

        updated_task = task.model_copy(update=task_update.model_dump(exclude_unset=True))
        tasks[index] = updated_task
        return updated_task

    raise HTTPException(status_code=404, detail="Task not found")


@app.delete("/tasks/{task_id}", response_model=Task)
async def delete_task(
    task_id: int,
    _: str = Depends(require_api_key),
):
    for index, task in enumerate(tasks):
        if task.id != task_id:
            continue

        return tasks.pop(index)

    raise HTTPException(status_code=404, detail="Task not found")
