from fastapi import Depends, FastAPI, HTTPException, Response
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
    filtered_tasks = tasks
    if status:
        filtered_tasks = [task for task in filtered_tasks if task.status == status]
    if priority is not None:
        filtered_tasks = [
            task for task in filtered_tasks if task.priority == priority
        ]
    if assigned_to:
        filtered_tasks = [
            task for task in filtered_tasks if task.assigned_to == assigned_to
        ]

    start_index = (page - 1) * page_size
    end_index = start_index + page_size
    return filtered_tasks[start_index:end_index]


@app.get("/tasks/{task_id}", response_model=Task)
async def get_task(task_id: int):
    for task in tasks:
        if task.id == task_id:
            return task
    raise HTTPException(status_code=404, detail="Task not found")


@app.post("/tasks", response_model=Task, status_code=201)
async def create_task(
    task: TaskCreate, username: str = Depends(require_api_key)
):
    if not any(p.id == task.project_id for p in projects):
        raise HTTPException(status_code=404, detail="Project not found")
    new_id = max(t.id for t in tasks) + 1 if tasks else 1
    new_task = Task(id=new_id, **task.dict())
    tasks.append(new_task)
    return new_task


@app.put("/tasks/{task_id}", response_model=Task)
async def update_task(
    task_id: int,
    task_update: TaskUpdate,
    username: str = Depends(require_api_key),
):
    for task in tasks:
        if task.id == task_id:
            update_data = task_update.dict(exclude_unset=True)
            for key, value in update_data.items():
                setattr(task, key, value)
            return task
    raise HTTPException(status_code=404, detail="Task not found")


@app.delete("/tasks/{task_id}", status_code=204)
async def delete_task(task_id: int, username: str = Depends(require_api_key)):
    global tasks
    task_to_delete = None
    for task in tasks:
        if task.id == task_id:
            task_to_delete = task
            break
    if not task_to_delete:
        raise HTTPException(status_code=404, detail="Task not found")
    tasks.remove(task_to_delete)
    return Response(status_code=204)
