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
    filtered_tasks = tasks
    if status is not None:
        filtered_tasks = [t for t in filtered_tasks if t.status == status]
    if priority is not None:
        filtered_tasks = [t for t in filtered_tasks if t.priority == priority]
    if assigned_to is not None:
        filtered_tasks = [t for t in filtered_tasks if t.assigned_to == assigned_to]

    if page < 1:
        raise HTTPException(status_code=400, detail="page must be >= 1")
    if page_size < 1:
        raise HTTPException(status_code=400, detail="page_size must be >= 1")

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
    if not any(p.id == task_in.project_id for p in projects):
        raise HTTPException(status_code=404, detail="Project not found")

    next_id = max((t.id for t in tasks), default=0) + 1
    task = Task(id=next_id, **task_in.model_dump())
    tasks.append(task)
    return task


@app.put("/tasks/{task_id}", response_model=Task)
async def update_task(task_id: int, patch: TaskUpdate, username: str = Depends(require_api_key)):
    for idx, task in enumerate(tasks):
        if task.id != task_id:
            continue

        update_data = patch.model_dump(exclude_unset=True)
        updated = task.model_copy(update=update_data)
        tasks[idx] = updated
        return updated

    raise HTTPException(status_code=404, detail="Task not found")


@app.delete("/tasks/{task_id}")
async def delete_task(task_id: int, username: str = Depends(require_api_key)):
    for idx, task in enumerate(tasks):
        if task.id == task_id:
            del tasks[idx]
            return {"ok": True}

    raise HTTPException(status_code=404, detail="Task not found")
