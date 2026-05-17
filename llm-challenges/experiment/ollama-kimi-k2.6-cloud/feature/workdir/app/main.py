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
    filtered = tasks
    if status is not None:
        filtered = [task for task in filtered if task.status == status]
    if priority is not None:
        filtered = [task for task in filtered if task.priority == priority]
    if assigned_to is not None:
        filtered = [task for task in filtered if task.assigned_to == assigned_to]

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
async def create_task(payload: TaskCreate, user: str = Depends(require_api_key)):
    project_found = False
    for project in projects:
        if project.id == payload.project_id:
            project_found = True
            break
    if not project_found:
        raise HTTPException(status_code=404, detail="Project not found")

    new_id = max((task.id for task in tasks), default=0) + 1
    task = Task(id=new_id, **payload.model_dump())
    tasks.append(task)
    return task


@app.put("/tasks/{task_id}", response_model=Task)
async def update_task(
    task_id: int,
    payload: TaskUpdate,
    user: str = Depends(require_api_key),
):
    for task in tasks:
        if task.id == task_id:
            updated_data = task.dict()
            updated_data.update(payload.model_dump(exclude_unset=True))
            updated_task = Task(**updated_data)
            tasks[tasks.index(task)] = updated_task
            return updated_task
    raise HTTPException(status_code=404, detail="Task not found")


@app.delete("/tasks/{task_id}", status_code=204)
async def delete_task(task_id: int, user: str = Depends(require_api_key)):
    for task in tasks:
        if task.id == task_id:
            tasks.remove(task)
            return
    raise HTTPException(status_code=404, detail="Task not found")
