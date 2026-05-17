from typing import Annotated, List

from fastapi import Depends, FastAPI, HTTPException, Query, status

from .auth import require_api_key
from .database import projects, tasks
from .models import Project, Task, TaskCreate, TaskStatus, TaskUpdate

app = FastAPI(title="Project Management API")


@app.get("/projects", response_model=List[Project])
async def list_projects():
    return projects


@app.get("/tasks", response_model=List[Task])
async def list_tasks(
    status_filter: Annotated[TaskStatus | None, Query(alias="status")] = None,
    priority: int | None = None,
    assigned_to: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1),
):
    filtered_tasks = tasks

    if status_filter is not None:
        filtered_tasks = [task for task in filtered_tasks if task.status == status_filter]
    if priority is not None:
        filtered_tasks = [task for task in filtered_tasks if task.priority == priority]
    if assigned_to is not None:
        filtered_tasks = [task for task in filtered_tasks if task.assigned_to == assigned_to]

    start_index = (page - 1) * page_size
    end_index = start_index + page_size
    return filtered_tasks[start_index:end_index]


@app.get("/tasks/{task_id}", response_model=Task)
async def get_task(task_id: int):
    return find_task_or_404(task_id)


@app.post("/tasks", response_model=Task, status_code=status.HTTP_201_CREATED)
async def create_task(
    task_data: TaskCreate,
    _: Annotated[str, Depends(require_api_key)],
):
    validate_project_exists(task_data.project_id)

    task = Task(id=get_next_task_id(), **task_data.model_dump())
    tasks.append(task)
    return task


@app.put("/tasks/{task_id}", response_model=Task)
async def update_task(
    task_id: int,
    task_update: TaskUpdate,
    _: Annotated[str, Depends(require_api_key)],
):
    task = find_task_or_404(task_id)
    updated_task = task.model_copy(update=task_update.model_dump(exclude_unset=True))

    for index, existing_task in enumerate(tasks):
        if existing_task.id == task_id:
            tasks[index] = updated_task
            return updated_task

    raise HTTPException(status_code=404, detail="Task not found")


@app.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: int,
    _: Annotated[str, Depends(require_api_key)],
):
    find_task_or_404(task_id)

    for index, task in enumerate(tasks):
        if task.id == task_id:
            tasks.pop(index)
            return None

    raise HTTPException(status_code=404, detail="Task not found")


def find_task_or_404(task_id: int) -> Task:
    for task in tasks:
        if task.id == task_id:
            return task
    raise HTTPException(status_code=404, detail="Task not found")


def validate_project_exists(project_id: int) -> None:
    for project in projects:
        if project.id == project_id:
            return
    raise HTTPException(status_code=404, detail="Project not found")


def get_next_task_id() -> int:
    if not tasks:
        return 1
    return max(task.id for task in tasks) + 1
