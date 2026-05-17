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
    filtered_tasks: List[Task] = []
    for task in tasks:
        if status is not None and task.status != status:
            continue
        if priority is not None and task.priority != priority:
            continue
        if assigned_to is not None and task.assigned_to != assigned_to:
            continue
        filtered_tasks.append(task)

    if page < 1:
        raise HTTPException(status_code=422, detail="page must be >= 1")
    if page_size < 1:
        raise HTTPException(status_code=422, detail="page_size must be >= 1")

    start = (page - 1) * page_size
    end = start + page_size
    return filtered_tasks[start:end]


@app.get("/tasks/{task_id}", response_model=Task)
async def get_task(task_id: int):
    for task in tasks:
        if task.id == task_id:
            return task
    raise HTTPException(status_code=404, detail="Task not found")


@app.post("/tasks", response_model=Task)
async def create_task(task_in: TaskCreate, username: str = Depends(require_api_key)):
    project_exists = any(p.id == task_in.project_id for p in projects)
    if not project_exists:
        raise HTTPException(status_code=404, detail="Project not found")

    next_id = max((t.id for t in tasks), default=0) + 1
    task = Task(id=next_id, **task_in.model_dump())
    tasks.append(task)
    return task


@app.put("/tasks/{task_id}", response_model=Task)
async def update_task(
    task_id: int,
    task_in: TaskUpdate,
    username: str = Depends(require_api_key),
):
    for idx, task in enumerate(tasks):
        if task.id != task_id:
            continue

        updated = task.model_copy(update=task_in.model_dump(exclude_unset=True))
        tasks[idx] = updated
        return updated

    raise HTTPException(status_code=404, detail="Task not found")


@app.delete("/tasks/{task_id}")
async def delete_task(task_id: int, username: str = Depends(require_api_key)):
    for idx, task in enumerate(tasks):
        if task.id == task_id:
            tasks.pop(idx)
            return {"ok": True}

    raise HTTPException(status_code=404, detail="Task not found")
