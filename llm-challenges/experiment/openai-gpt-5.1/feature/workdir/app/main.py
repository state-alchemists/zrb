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
    page_size: int = 20,
):
    # Filter tasks
    filtered_tasks = tasks
    if status is not None:
        filtered_tasks = [t for t in filtered_tasks if t.status == status]
    if priority is not None:
        filtered_tasks = [t for t in filtered_tasks if t.priority == priority]
    if assigned_to is not None:
        filtered_tasks = [t for t in filtered_tasks if t.assigned_to == assigned_to]

    # Pagination
    if page < 1:
        page = 1
    if page_size < 1:
        page_size = 20
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
async def create_task(payload: TaskCreate, username: str = Depends(require_api_key)):
    # Validate project_id exists
    for project in projects:
        if project.id == payload.project_id:
            break
    else:
        raise HTTPException(status_code=404, detail="Project not found")

    # Auto-generate unique ID
    if tasks:
        new_id = max(task.id for task in tasks) + 1
    else:
        new_id = 1

    task = Task(
        id=new_id,
        title=payload.title,
        status=payload.status,
        priority=payload.priority,
        project_id=payload.project_id,
        assigned_to=payload.assigned_to,
    )
    tasks.append(task)
    return task


@app.put("/tasks/{task_id}", response_model=Task)
async def update_task(task_id: int, payload: TaskUpdate, username: str = Depends(require_api_key)):
    for index, task in enumerate(tasks):
        if task.id == task_id:
            updated_data = task.dict()
            if payload.title is not None:
                updated_data["title"] = payload.title
            if payload.status is not None:
                updated_data["status"] = payload.status
            if payload.priority is not None:
                updated_data["priority"] = payload.priority
            if payload.assigned_to is not None:
                updated_data["assigned_to"] = payload.assigned_to
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
