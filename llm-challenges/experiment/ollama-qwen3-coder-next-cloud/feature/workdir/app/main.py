from fastapi import FastAPI, HTTPException, Query
from typing import List, Optional
from .models import Task, TaskCreate, TaskUpdate, Project
from .database import tasks, projects, VALID_API_KEYS
from .auth import require_api_key

app = FastAPI(title="Project Management API")


@app.get("/projects", response_model=List[Project])
async def list_projects():
    return projects


@app.get("/tasks", response_model=List[Task])
async def list_tasks(
    status: Optional[str] = Query(None),
    priority: Optional[int] = Query(None),
    assigned_to: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    filtered = tasks

    if status is not None:
        filtered = [t for t in filtered if t.status.value == status]
    if priority is not None:
        filtered = [t for t in filtered if t.priority == priority]
    if assigned_to is not None:
        filtered = [t for t in filtered if t.assigned_to == assigned_to]

    total = len(filtered)
    start = (page - 1) * page_size
    end = start + page_size
    paginated = filtered[start:end]

    return paginated


@app.get("/tasks/{task_id}", response_model=Task)
async def get_task(task_id: int):
    for task in tasks:
        if task.id == task_id:
            return task
    raise HTTPException(status_code=404, detail="Task not found")


@app.post("/tasks", response_model=Task, status_code=201)
async def create_task(
    task: TaskCreate,
    api_user: str = Query(..., alias="api_user"),
):
    # Validate project_id exists
    project_ids = {p.id for p in projects}
    if task.project_id not in project_ids:
        raise HTTPException(status_code=404, detail="Project not found")

    # Auto-generate unique ID
    max_id = max((t.id for t in tasks), default=0)
    new_id = max_id + 1

    new_task = Task(
        id=new_id,
        title=task.title,
        status=task.status,
        priority=task.priority,
        project_id=task.project_id,
        assigned_to=task.assigned_to,
    )
    tasks.append(new_task)
    return new_task


@app.put("/tasks/{task_id}", response_model=Task)
async def update_task(
    task_id: int,
    task_update: TaskUpdate,
    api_user: str = Query(..., alias="api_user"),
):
    for i, task in enumerate(tasks):
        if task.id == task_id:
            update_data = task_update.dict(exclude_unset=True)
            updated_task = task.copy(update=update_data)
            tasks[i] = updated_task
            return updated_task
    raise HTTPException(status_code=404, detail="Task not found")


@app.delete("/tasks/{task_id}", status_code=204)
async def delete_task(
    task_id: int,
    api_user: str = Query(..., alias="api_user"),
):
    for i, task in enumerate(tasks):
        if task.id == task_id:
            tasks.pop(i)
            return None
    raise HTTPException(status_code=404, detail="Task not found")
