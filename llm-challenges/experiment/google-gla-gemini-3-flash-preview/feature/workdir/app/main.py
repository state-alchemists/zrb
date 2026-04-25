from fastapi import FastAPI, HTTPException, Depends
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
    page: int = 1,
    page_size: int = 20
):
    filtered_tasks = tasks
    if status:
        filtered_tasks = [t for t in filtered_tasks if t.status == status]
    if priority is not None:
        filtered_tasks = [t for t in filtered_tasks if t.priority == priority]
    if assigned_to:
        filtered_tasks = [t for t in filtered_tasks if t.assigned_to == assigned_to]

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
async def create_task(task_data: TaskCreate, username: str = Depends(require_api_key)):
    project_exists = any(p.id == task_data.project_id for p in projects)
    if not project_exists:
        raise HTTPException(status_code=404, detail="Project not found")

    new_id = max((t.id for t in tasks), default=0) + 1
    new_task = Task(
        id=new_id,
        title=task_data.title,
        status=task_data.status,
        priority=task_data.priority,
        project_id=task_data.project_id,
        assigned_to=task_data.assigned_to
    )
    tasks.append(new_task)
    return new_task


@app.put("/tasks/{task_id}", response_model=Task)
async def update_task(task_id: int, task_data: TaskUpdate, username: str = Depends(require_api_key)):
    for task in tasks:
        if task.id == task_id:
            if task_data.title is not None:
                task.title = task_data.title
            if task_data.status is not None:
                task.status = task_data.status
            if task_data.priority is not None:
                task.priority = task_data.priority
            if task_data.assigned_to is not None:
                task.assigned_to = task_data.assigned_to
            return task
    raise HTTPException(status_code=404, detail="Task not found")


@app.delete("/tasks/{task_id}")
async def delete_task(task_id: int, username: str = Depends(require_api_key)):
    for i, task in enumerate(tasks):
        if task.id == task_id:
            tasks.pop(i)
            return {"detail": "Task deleted"}
    raise HTTPException(status_code=404, detail="Task not found")
