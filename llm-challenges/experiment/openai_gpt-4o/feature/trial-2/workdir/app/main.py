from fastapi import FastAPI, HTTPException
from typing import List
from .models import Task, TaskCreate, TaskUpdate, Project
from .database import tasks, projects
from .auth import require_api_key

app = FastAPI(title="Project Management API")


@app.get("/projects", response_model=List[Project])
async def list_projects():
    return projects


@app.get("/tasks", response_model=List[Task])
async def list_tasks(status: Optional[str] = None, priority: Optional[str] = None, assigned_to: Optional[str] = None, page: int = 1, page_size: int = 20):
    filtered_tasks = [task for task in tasks if
        (status is None or task.status == status) and
        (priority is None or task.priority == priority) and
        (assigned_to is None or task.assigned_to == assigned_to)
    ]
    start = (page - 1) * page_size
    end = start + page_size
    return filtered_tasks[start:end]


@app.get("/tasks/{task_id}", response_model=Task)
async def get_task(task_id: int):
    for task in tasks:
        if task.id == task_id:
            return task
    raise HTTPException(status_code=404, detail="Task not found")


@app.post("/tasks", response_model=Task, dependencies=[Depends(require_api_key)])
async def create_task(task: TaskCreate):
    if not any(project.id == task.project_id for project in projects):
        raise HTTPException(status_code=404, detail="Project not found")
    new_task_id = max(task.id for task in tasks) + 1 if tasks else 1
    new_task = Task(id=new_task_id, **task.dict())
    tasks.append(new_task)
    return new_task
@app.put("/tasks/{task_id}", response_model=Task, dependencies=[Depends(require_api_key)])
async def update_task(task_id: int, task_update: TaskUpdate):
    for task in tasks:
        if task.id == task_id:
            task_data = task.dict()
            update_data = task_update.dict(exclude_unset=True)
            task_data.update(update_data)
            updated_task = Task(**task_data)
            tasks[tasks.index(task)] = updated_task
            return updated_task
    raise HTTPException(status_code=404, detail="Task not found")
@app.delete("/tasks/{task_id}", response_model=None, dependencies=[Depends(require_api_key)])
async def delete_task(task_id: int):
    for task in tasks:
        if task.id == task_id:
            tasks.remove(task)
            return
    raise HTTPException(status_code=404, detail="Task not found")
