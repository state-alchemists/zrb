from fastapi import FastAPI, HTTPException, Depends, Query
from typing import List, Optional
from .models import Task, TaskCreate, TaskUpdate, Project, TaskStatus
from .database import tasks, projects
from .auth import require_api_key

app = FastAPI(title="Project Management API")


def _next_task_id() -> int:
    return max(t.id for t in tasks) + 1 if tasks else 1


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
async def create_task(task_in: TaskCreate, _user: str = Depends(require_api_key)):
    if not any(p.id == task_in.project_id for p in projects):
        raise HTTPException(status_code=404, detail="Project not found")
    new_task = Task(id=_next_task_id(), **task_in.model_dump())
    tasks.append(new_task)
    return new_task


@app.put("/tasks/{task_id}", response_model=Task)
async def update_task(task_id: int, task_in: TaskUpdate, _user: str = Depends(require_api_key)):
    for task in tasks:
        if task.id == task_id:
            updated = task.model_copy(update=task_in.model_dump(exclude_unset=True))
            tasks[tasks.index(task)] = updated
            return updated
    raise HTTPException(status_code=404, detail="Task not found")


@app.delete("/tasks/{task_id}", status_code=204)
async def delete_task(task_id: int, _user: str = Depends(require_api_key)):
    for i, task in enumerate(tasks):
        if task.id == task_id:
            tasks.pop(i)
            return
    raise HTTPException(status_code=404, detail="Task not found")
