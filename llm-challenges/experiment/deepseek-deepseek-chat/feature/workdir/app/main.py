from fastapi import FastAPI, HTTPException, Depends
from typing import Optional, List
from .models import Task, TaskCreate, TaskUpdate, TaskStatus, Project
from .database import tasks, projects
from .auth import require_api_key

app = FastAPI(title="Project Management API")

_next_id = len(tasks) + 1


def _get_next_id() -> int:
    global _next_id
    tid = _next_id
    _next_id += 1
    return tid


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


@app.post("/tasks", response_model=Task, dependencies=[Depends(require_api_key)])
async def create_task(task_data: TaskCreate):
    if not any(p.id == task_data.project_id for p in projects):
        raise HTTPException(status_code=404, detail="Project not found")
    task = Task(id=_get_next_id(), **task_data.model_dump())
    tasks.append(task)
    return task


@app.put("/tasks/{task_id}", response_model=Task, dependencies=[Depends(require_api_key)])
async def update_task(task_id: int, update: TaskUpdate):
    for task in tasks:
        if task.id == task_id:
            update_data = update.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                setattr(task, field, value)
            return task
    raise HTTPException(status_code=404, detail="Task not found")


@app.delete("/tasks/{task_id}", dependencies=[Depends(require_api_key)])
async def delete_task(task_id: int):
    for i, task in enumerate(tasks):
        if task.id == task_id:
            tasks.pop(i)
            return {"detail": "Task deleted"}
    raise HTTPException(status_code=404, detail="Task not found")
