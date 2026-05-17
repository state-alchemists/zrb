from fastapi import FastAPI, HTTPException, Depends, Query
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
    status: Optional[TaskStatus] = Query(default=None),
    priority: Optional[int] = Query(default=None),
    assigned_to: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1),
):
    # Apply filters
    filtered = tasks
    if status is not None:
        filtered = [t for t in filtered if t.status == status]
    if priority is not None:
        filtered = [t for t in filtered if t.priority == priority]
    if assigned_to is not None:
        filtered = [t for t in filtered if t.assigned_to == assigned_to]
    # Apply pagination
    start = (page - 1) * page_size
    end = start + page_size
    return filtered[start:end]


@app.get("/tasks/{task_id}", response_model=Task)
async def get_task(task_id: int):
    for task in tasks:
        if task.id == task_id:
            return task
    raise HTTPException(status_code=404, detail="Task not found")


@app.post("/tasks", response_model=Task, status_code=201)
async def create_task(
    task_data: TaskCreate,
    username: str = Depends(require_api_key),
):
    # Validate project_id exists
    project_ids = {p.id for p in projects}
    if task_data.project_id not in project_ids:
        raise HTTPException(status_code=404, detail="Project not found")
    # Auto-generate unique ID
    existing_ids = {t.id for t in tasks}
    new_id = max(existing_ids) + 1 if existing_ids else 1
    new_task = Task(id=new_id, **task_data.model_dump())
    tasks.append(new_task)
    return new_task


@app.put("/tasks/{task_id}", response_model=Task)
async def update_task(
    task_id: int,
    task_data: TaskUpdate,
    username: str = Depends(require_api_key),
):
    for task in tasks:
        if task.id == task_id:
            update_dict = task_data.model_dump(exclude_unset=True)
            for key, value in update_dict.items():
                setattr(task, key, value)
            return task
    raise HTTPException(status_code=404, detail="Task not found")


@app.delete("/tasks/{task_id}", status_code=204)
async def delete_task(
    task_id: int,
    username: str = Depends(require_api_key),
):
    for i, task in enumerate(tasks):
        if task.id == task_id:
            tasks.pop(i)
            return None
    raise HTTPException(status_code=404, detail="Task not found")
