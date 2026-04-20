from fastapi import Depends, FastAPI, HTTPException
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
    page: int = 1,
    page_size: int = 20,
):
    """List tasks with optional filtering and pagination."""
    # Start from all tasks
    filtered_tasks = tasks

    # Apply filters if provided
    if status is not None:
        filtered_tasks = [t for t in filtered_tasks if t.status == status]
    if priority is not None:
        filtered_tasks = [t for t in filtered_tasks if t.priority == priority]
    if assigned_to is not None:
        filtered_tasks = [t for t in filtered_tasks if t.assigned_to == assigned_to]

    # Basic guardrails for pagination
    if page < 1:
        page = 1
    if page_size < 1:
        page_size = 1

    start = (page - 1) * page_size
    end = start + page_size
    return filtered_tasks[start:end]


@app.get("/tasks/{task_id}", response_model=Task)
async def get_task(task_id: int):
    for task in tasks:
        if task.id == task_id:
            return task
    raise HTTPException(status_code=404, detail="Task not found")


@app.post("/tasks", response_model=Task, status_code=201)
async def create_task(task_in: TaskCreate, username: str = Depends(require_api_key)):
    """Create a task.

    - Requires a valid API key.
    - Validates that the referenced project exists.
    - Auto-generates a unique integer task id.
    """
    # Validate project exists
    if not any(project.id == task_in.project_id for project in projects):
        raise HTTPException(status_code=404, detail="Project not found")

    # Generate unique id
    if tasks:
        new_id = max(task.id for task in tasks) + 1
    else:
        new_id = 1

    new_task = Task(id=new_id, **task_in.dict())
    tasks.append(new_task)
    return new_task


@app.put("/tasks/{task_id}", response_model=Task)
async def update_task(
    task_id: int,
    task_update: TaskUpdate,
    username: str = Depends(require_api_key),
):
    """Partially update a task (requires auth)."""
    for index, task in enumerate(tasks):
        if task.id == task_id:
            updated_fields = task_update.dict(exclude_unset=True)
            updated_task = task.copy(update=updated_fields)
            tasks[index] = updated_task
            return updated_task
    raise HTTPException(status_code=404, detail="Task not found")


@app.delete("/tasks/{task_id}", status_code=204)
async def delete_task(task_id: int, username: str = Depends(require_api_key)):
    """Delete a task (requires auth)."""
    for index, task in enumerate(tasks):
        if task.id == task_id:
            del tasks[index]
            return
    raise HTTPException(status_code=404, detail="Task not found")
