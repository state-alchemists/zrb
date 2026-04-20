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
    status: Optional[TaskStatus] = None,
    priority: Optional[int] = None,
    assigned_to: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1)
):
    result = tasks
    if status is not None:
        result = [t for t in result if t.status == status]
    if priority is not None:
        result = [t for t in result if t.priority == priority]
    if assigned_to is not None:
        result = [t for t in result if t.assigned_to == assigned_to]
    
    start = (page - 1) * page_size
    end = start + page_size
    return result[start:end]


@app.get("/tasks/{task_id}", response_model=Task)
async def get_task(task_id: int):
    for task in tasks:
        if task.id == task_id:
            return task
    raise HTTPException(status_code=404, detail="Task not found")


@app.post("/tasks", response_model=Task)
async def create_task(task_in: TaskCreate, user: str = Depends(require_api_key)):
    if not any(p.id == task_in.project_id for p in projects):
        raise HTTPException(status_code=404, detail="Project not found")
    
    new_id = max((t.id for t in tasks), default=0) + 1
    new_task = Task(
        id=new_id,
        title=task_in.title,
        status=task_in.status,
        priority=task_in.priority,
        project_id=task_in.project_id,
        assigned_to=task_in.assigned_to
    )
    tasks.append(new_task)
    return new_task


@app.put("/tasks/{task_id}", response_model=Task)
async def update_task(task_id: int, task_in: TaskUpdate, user: str = Depends(require_api_key)):
    for task in tasks:
        if task.id == task_id:
            if task_in.title is not None:
                task.title = task_in.title
            if task_in.status is not None:
                task.status = task_in.status
            if task_in.priority is not None:
                task.priority = task_in.priority
            if task_in.assigned_to is not None:
                task.assigned_to = task_in.assigned_to
            return task
    raise HTTPException(status_code=404, detail="Task not found")


@app.delete("/tasks/{task_id}")
async def delete_task(task_id: int, user: str = Depends(require_api_key)):
    for i, task in enumerate(tasks):
        if task.id == task_id:
            del tasks[i]
            return {"detail": "Task deleted"}
    raise HTTPException(status_code=404, detail="Task not found")
