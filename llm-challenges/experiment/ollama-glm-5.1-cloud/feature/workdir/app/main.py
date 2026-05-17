from fastapi import FastAPI, HTTPException, Depends, Response
from typing import List, Optional
from .models import Task, TaskCreate, TaskUpdate, TaskStatus, Project
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
async def create_task(task_in: TaskCreate, username: str = Depends(require_api_key)):
    project_ids = {p.id for p in projects}
    if task_in.project_id not in project_ids:
        raise HTTPException(status_code=404, detail="Project not found")
    new_id = max((t.id for t in tasks), default=0) + 1
    task = Task(id=new_id, **task_in.model_dump())
    tasks.append(task)
    return task


@app.put("/tasks/{task_id}", response_model=Task)
async def update_task(
    task_id: int, task_in: TaskUpdate, username: str = Depends(require_api_key)
):
    for task in tasks:
        if task.id == task_id:
            update_data = task_in.model_dump(exclude_unset=True)
            updated = task.model_copy(update=update_data)
            tasks[tasks.index(task)] = updated
            return updated
    raise HTTPException(status_code=404, detail="Task not found")


@app.delete("/tasks/{task_id}", status_code=204)
async def delete_task(task_id: int, username: str = Depends(require_api_key)):
    for i, task in enumerate(tasks):
        if task.id == task_id:
            tasks.pop(i)
            return Response(status_code=204)
    raise HTTPException(status_code=404, detail="Task not found")