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
    filtered = tasks
    if status is not None:
        filtered = [t for t in filtered if t.status == status]
    if priority is not None:
        filtered = [t for t in filtered if t.priority == priority]
    if assigned_to is not None:
        filtered = [t for t in filtered if t.assigned_to == assigned_to]
    
    start = (page - 1) * page_size
    end = start + page_size
    return filtered[start:end]


@app.get("/tasks/{task_id}", response_model=Task)
async def get_task(task_id: int):
    for task in tasks:
        if task.id == task_id:
            return task
    raise HTTPException(status_code=404, detail="Task not found")


@app.post("/tasks", response_model=Task)
async def create_task(task: TaskCreate, current_user: str = Depends(require_api_key)):
    if not any(p.id == task.project_id for p in projects):
        raise HTTPException(status_code=404, detail="Project not found")
    
    new_id = max((t.id for t in tasks), default=0) + 1
    new_task = Task(id=new_id, **task.model_dump())
    tasks.append(new_task)
    return new_task


@app.put("/tasks/{task_id}", response_model=Task)
async def update_task(task_id: int, task_update: TaskUpdate, current_user: str = Depends(require_api_key)):
    for task in tasks:
        if task.id == task_id:
            update_data = task_update.model_dump(exclude_unset=True)
            for key, value in update_data.items():
                setattr(task, key, value)
            return task
    raise HTTPException(status_code=404, detail="Task not found")


@app.delete("/tasks/{task_id}")
async def delete_task(task_id: int, current_user: str = Depends(require_api_key)):
    for i, task in enumerate(tasks):
        if task.id == task_id:
            del tasks[i]
            return {"detail": "Task deleted"}
    raise HTTPException(status_code=404, detail="Task not found")
