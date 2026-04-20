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
    page_size: int = Query(default=20, ge=1, le=100),
):
    """List tasks with optional filtering and pagination."""
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
    _: str = Depends(require_api_key),
):
    """Create a new task. Requires authentication."""
    # Validate project_id exists
    project_ids = {p.id for p in projects}
    if task_create.project_id not in project_ids:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Auto-generate unique ID
    if tasks:
        new_id = max(t.id for t in tasks) + 1
    else:
        new_id = 1
    
    new_task = Task(id=new_id, **task_create.model_dump())
    tasks.append(new_task)
    return new_task


@app.put("/tasks/{task_id}", response_model=Task)
async def update_task(
    task_id: int,
    task_update: TaskUpdate,
    _: str = Depends(require_api_key),
):
    """Partial update of a task. Requires authentication."""
    for i, task in enumerate(tasks):
        if task.id == task_id:
            update_data = task_update.model_dump(exclude_unset=True)
            updated_task = task.model_copy(update=update_data)
            tasks[i] = updated_task
            return updated_task
    raise HTTPException(status_code=404, detail="Task not found")


@app.delete("/tasks/{task_id}", status_code=204)
async def delete_task(
    task_id: int,
    _: str = Depends(require_api_key),
):
    """Delete a task. Requires authentication."""
    for i, task in enumerate(tasks):
        if task.id == task_id:
            tasks.pop(i)
            return None
    raise HTTPException(status_code=404, detail="Task not found")
