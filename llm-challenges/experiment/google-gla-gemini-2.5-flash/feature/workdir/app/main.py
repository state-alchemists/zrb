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
from fastapi import FastAPI, HTTPException, Query
from typing import List, Optional
from fastapi import Depends
from .models import Task, TaskCreate, TaskUpdate, Project, TaskStatus
from .database import tasks, projects
from .auth import require_api_key

app = FastAPI(title="Project Management API")


@app.get("/projects", response_model=List[Project])
async def list_projects():
    return projects


@app.get("/tasks", response_model=List[Task])
async def list_tasks(
    status: Optional[TaskStatus] = Query(None),
    priority: Optional[int] = Query(None),
    assigned_to: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100)
):
    filtered_tasks = tasks
    if status:
        filtered_tasks = [task for task in filtered_tasks if task.status == status]
    if priority:
        filtered_tasks = [task for task in filtered_tasks if task.priority == priority]
    if assigned_to:
        filtered_tasks = [task for task in filtered_tasks if task.assigned_to == assigned_to]

    # Apply pagination
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
async def create_task(task: TaskCreate, api_key: str = Depends(require_api_key)):
    project_exists = any(p.id == task.project_id for p in projects)
    if not project_exists:
        raise HTTPException(status_code=404, detail="Project not found")

    new_id = max([t.id for t in tasks]) + 1 if tasks else 1
    new_task = Task(id=new_id, **task.dict())
    tasks.append(new_task)
    return new_task


@app.put("/tasks/{task_id}", response_model=Task)
async def update_task(task_id: int, task_update: TaskUpdate, api_key: str = Depends(require_api_key)):
    for idx, task in enumerate(tasks):
        if task.id == task_id:
            updated_data = task_update.dict(exclude_unset=True)
            for key, value in updated_data.items():
                setattr(tasks[idx], key, value)
            return tasks[idx]
    raise HTTPException(status_code=404, detail="Task not found")


@app.delete("/tasks/{task_id}", status_code=204)
async def delete_task(task_id: int, api_key: str = Depends(require_api_key)):
    original_len = len(tasks)
    tasks[:] = [task for task in tasks if task.id != task_id]
    if len(tasks) == original_len:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"message": "Task deleted successfully"}
