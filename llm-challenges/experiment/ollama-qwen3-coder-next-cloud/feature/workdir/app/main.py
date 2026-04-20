from fastapi import FastAPI, HTTPException, Query
from typing import List, Optional
from .models import Task, TaskCreate, TaskUpdate, Project, TaskStatus
from .database import tasks, projects, filter_tasks, paginate_tasks, create_task, find_task_by_id
from .auth import require_api_key

app = FastAPI(title="Project Management API")


@app.get("/projects", response_model=List[Project])
async def list_projects():
    return projects


@app.get("/tasks", response_model=List[Task])
async def list_tasks(
    status: Optional[TaskStatus] = Query(None),
    priority: Optional[int] = Query(None),
    assigned_to: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    filtered = filter_tasks(tasks, status=status, priority=priority, assigned_to=assigned_to)
    paginated = paginate_tasks(filtered, page=page, page_size=page_size)
    return paginated


@app.get("/tasks/{task_id}", response_model=Task)
async def get_task(task_id: int):
    for task in tasks:
        if task.id == task_id:
            return task
    raise HTTPException(status_code=404, detail="Task not found")


# POST /tasks — create a task (requires auth, validate project_id, auto-generate id)
@app.post("/tasks", response_model=Task)
async def create_new_task(
    task_create: TaskCreate,
    api_key: str = require_api_key,
):
    # Validate project_id exists
    project_ids = {p.id for p in projects}
    if task_create.project_id not in project_ids:
        raise HTTPException(status_code=404, detail="Project not found")
    
    task = Task(
        title=task_create.title,
        status=task_create.status,
        priority=task_create.priority,
        project_id=task_create.project_id,
        assigned_to=task_create.assigned_to,
    )
    created = create_task(task)
    return created


# PUT /tasks/{task_id} — partial update (requires auth, 404 if not found)
@app.put("/tasks/{task_id}", response_model=Task)
async def update_task(
    task_id: int,
    task_update: TaskUpdate,
    api_key: str = require_api_key,
):
    task = find_task_by_id(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    
    update_data = task_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(task, field, value)
    return task


# DELETE /tasks/{task_id} — delete a task (requires auth, 404 if not found)
@app.delete("/tasks/{task_id}", response_model=Task)
async def delete_task(
    task_id: int,
    api_key: str = require_api_key,
):
    task = find_task_by_id(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    
    tasks.remove(task)
    return task
