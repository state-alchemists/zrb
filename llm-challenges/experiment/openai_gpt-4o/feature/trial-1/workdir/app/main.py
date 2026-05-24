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
async def list_tasks(status: str = None, priority: str = None, assigned_to: str = None, page: int = 1, page_size: int = 20):
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


@app.post("/tasks", response_model=Task, dependencies=[require_api_key])
async def create_task(task: TaskCreate):
    if task.project_id not in [project.id for project in projects]:
        raise HTTPException(status_code=404, detail="Project ID not found")
    new_id = max((task.id for task in tasks), default=0) + 1
    new_task = Task(id=new_id, **task.dict())
    tasks.append(new_task)
    return new_task
# TODO: PUT /tasks/{task_id} — partial update (requires auth, 404 if not found)
# TODO: DELETE /tasks/{task_id} — delete a task (requires auth, 404 if not found)
