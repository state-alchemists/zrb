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
async def list_tasks():
    # TODO: add filtering (status, priority, assigned_to query params)
    # TODO: add pagination (page, page_size query params)
    return tasks


@app.get("/tasks/{task_id}", response_model=Task)
async def get_task(task_id: int):
    for task in tasks:
        if task.id == task_id:
            return task
    raise HTTPException(status_code=404, detail="Task not found")


# TODO: POST /tasks — create a task (requires auth, validate project_id, auto-generate id)
# TODO: PUT /tasks/{task_id} — partial update (requires auth, 404 if not found)
# TODO: DELETE /tasks/{task_id} — delete a task (requires auth, 404 if not found)
