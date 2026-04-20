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
    # Filtering
    filtered_tasks = tasks
    if status is not None:
        filtered_tasks = [t for t in filtered_tasks if t.status == status]
    if priority is not None:
        filtered_tasks = [t for t in filtered_tasks if t.priority == priority]
    if assigned_to is not None:
        filtered_tasks = [t for t in filtered_tasks if t.assigned_to == assigned_to]

    # Pagination
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
    # Validate project exists
    if not any(p.id == task_in.project_id for p in projects):
        raise HTTPException(status_code=404, detail="Project not found")

    # Generate unique id
    next_id = max((t.id for t in tasks), default=0) + 1

    task = Task(
        id=next_id,
        title=task_in.title,
        status=task_in.status,
        priority=task_in.priority,
        project_id=task_in.project_id,
        assigned_to=task_in.assigned_to,
    )
    tasks.append(task)
    return task


@app.put("/tasks/{task_id}", response_model=Task)
async def update_task(
    task_id: int,
    task_update: TaskUpdate,
    username: str = Depends(require_api_key),
):
    for index, task in enumerate(tasks):
        if task.id == task_id:
            updated_data = task.dict()
            update_fields = task_update.dict(exclude_unset=True)
            updated_data.update(update_fields)
            updated_task = Task(**updated_data)
            tasks[index] = updated_task
            return updated_task
    raise HTTPException(status_code=404, detail="Task not found")


@app.delete("/tasks/{task_id}")
async def delete_task(task_id: int, username: str = Depends(require_api_key)):
    for index, task in enumerate(tasks):
        if task.id == task_id:
            del tasks[index]
            return {"detail": "Task deleted"}
    raise HTTPException(status_code=404, detail="Task not found")
