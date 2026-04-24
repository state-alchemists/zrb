from fastapi import FastAPI, HTTPException, Query, Depends
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
    result = tasks
    
    # Apply filters
    if status is not None:
        result = [t for t in result if t.status == status]
    if priority is not None:
        result = [t for t in result if t.priority == priority]
    if assigned_to is not None:
        result = [t for t in result if t.assigned_to == assigned_to]
    
    # Apply pagination
    start = (page - 1) * page_size
    end = start + page_size
    return result[start:end]


@app.get("/tasks/{task_id}", response_model=Task)
async def get_task(task_id: int):
    for task in tasks:
        if task.id == task_id:
            return task
    raise HTTPException(status_code=404, detail="Task not found")


@app.post("/tasks", response_model=Task, status_code=201)
async def create_task(
    task_create: TaskCreate,
    username: str = Depends(require_api_key),
):
    # Validate project exists
    project_exists = any(p.id == task_create.project_id for p in projects)
    if not project_exists:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Generate unique ID
    max_id = max((t.id for t in tasks), default=0)
    new_id = max_id + 1
    
    # Create new task
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
async def update_task(
    task_id: int,
    task_update: TaskUpdate,
    username: str = Depends(require_api_key),
):
    # Find task
    task_index = None
    for i, task in enumerate(tasks):
        if task.id == task_id:
            task_index = i
            break
    
    if task_index is None:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Apply partial updates
    task = tasks[task_index]
    update_data = task_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(task, field, value)
    
    return task


@app.delete("/tasks/{task_id}", status_code=204)
async def delete_task(
    task_id: int,
    username: str = Depends(require_api_key),
):
    # Find and delete task
    for i, task in enumerate(tasks):
        if task.id == task_id:
            tasks.pop(i)
            return
    
    raise HTTPException(status_code=404, detail="Task not found")