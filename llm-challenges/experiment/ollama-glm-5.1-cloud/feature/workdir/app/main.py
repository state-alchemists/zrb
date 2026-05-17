from fastapi import Depends, FastAPI, HTTPException
from typing import List
from .models import Task, TaskCreate, TaskUpdate, TaskStatus, Project
from .database import tasks, projects
from .auth import require_api_key

app = FastAPI(title="Project Management API")


@app.get("/projects", response_model=List[Project])
async def list_projects():
    return projects


@app.get("/tasks", response_model=List[Task])
async def list_tasks(
    status: TaskStatus = None,
    priority: int = None,
    assigned_to: str = None,
    page: int = 1,
    page_size: int = 20,
):
    result = tasks
    if status is not None:
        result = [t for t in result if t.status == status]
    if priority is not None:
        result = [t for t in result if t.priority == priority]
    if assigned_to is not None:
        result = [t for t in result if t.assigned_to == assigned_to]
    start = (page - 1) * page_size
    return result[start : start + page_size]


@app.get("/tasks/{task_id}", response_model=Task)
async def get_task(task_id: int):
    for task in tasks:
        if task.id == task_id:
            return task
    raise HTTPException(status_code=404, detail="Task not found")


@app.post("/tasks", response_model=Task, status_code=201)
async def create_task(
    task: TaskCreate,
    username: str = Depends(require_api_key),
):
    project_ids = {p.id for p in projects}
    if task.project_id not in project_ids:
        raise HTTPException(status_code=404, detail="Project not found")
    new_id = max((t.id for t in tasks), default=0) + 1
    new_task = Task(id=new_id, **task.model_dump())
    tasks.append(new_task)
    return new_task


@app.put("/tasks/{task_id}", response_model=Task)
async def update_task(
    task_id: int,
    update: TaskUpdate,
    username: str = Depends(require_api_key),
):
    for idx, task in enumerate(tasks):
        if task.id == task_id:
            updated_task = task.model_copy(update=update.model_dump(exclude_unset=True))
            tasks[idx] = updated_task
            return updated_task
    raise HTTPException(status_code=404, detail="Task not found")


@app.delete("/tasks/{task_id}", response_model=Task)
async def delete_task(
    task_id: int,
    username: str = Depends(require_api_key),
):
    for idx, task in enumerate(tasks):
        if task.id == task_id:
            return tasks.pop(idx)
    raise HTTPException(status_code=404, detail="Task not found")