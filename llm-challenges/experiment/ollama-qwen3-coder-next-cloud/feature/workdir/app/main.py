from fastapi import FastAPI, HTTPException, Query
from typing import List, Optional
from .models import Task, TaskCreate, TaskUpdate, Project
from .database import tasks, projects
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
    
    if status:
        filtered = [t for t in filtered if t.status.value == status]
    if priority is not None:
        filtered = [t for t in filtered if t.priority == priority]
    if assigned_to:
        filtered = [t for t in filtered if t.assigned_to == assigned_to]
    
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
async def create_task(task_create: TaskCreate, username: str = require_api_key):
    # Validate project_id exists
    project_ids = {p.id for p in projects}
    if task_create.project_id not in project_ids:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Auto-generate unique ID
    new_id = max((t.id for t in tasks), default=0) + 1
    
    new_task = Task(
        id=new_id,
        title=task_create.title,
        status=task_create.status,
        priority=task_create.priority,
        project_id=task_create.project_id,
        assigned_to=task_create.assigned_to,
    )
    tasks.append(new_task)
    return new_task


@app.put("/tasks/{task_id}", response_model=Task)
async def update_task(task_id: int, task_update: TaskUpdate, username: str = require_api_key):
    for task in tasks:
        if task.id == task_id:
            # Apply partial updates
            if task_update.title is not None:
                task.title = task_update.title
            if task_update.status is not None:
                task.status = task_update.status
            if task_update.priority is not None:
                task.priority = task_update.priority
            if task_update.assigned_to is not None:
                task.assigned_to = task_update.assigned_to
            return task
    raise HTTPException(status_code=404, detail="Task not found")


@app.delete("/tasks/{task_id}", status_code=204)
async def delete_task(task_id: int, username: str = require_api_key):
    for i, task in enumerate(tasks):
        if task.id == task_id:
            tasks.pop(i)
            return
    raise HTTPException(status_code=404, detail="Task not found")
