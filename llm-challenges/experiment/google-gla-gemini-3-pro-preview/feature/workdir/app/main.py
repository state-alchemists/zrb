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


# TODO: POST /tasks — create a task (requires auth, validate project_id, auto-generate id)
@app.post("/tasks", response_model=Task)
async def create_task(task_in: TaskCreate, username: str = Depends(require_api_key)):
    project_exists = any(p.id == task_in.project_id for p in projects)
    if not project_exists:
        raise HTTPException(status_code=404, detail="Project not found")
        
    new_id = 1 if not tasks else max(t.id for t in tasks) + 1
    new_task = Task(id=new_id, **task_in.model_dump())
    tasks.append(new_task)
    return new_task


# TODO: PUT /tasks/{task_id} — partial update (requires auth, 404 if not found)
@app.put("/tasks/{task_id}", response_model=Task)
async def update_task(task_id: int, task_in: TaskUpdate, username: str = Depends(require_api_key)):
    for i, task in enumerate(tasks):
        if task.id == task_id:
            update_data = task_in.model_dump(exclude_unset=True)
            updated_task = task.model_copy(update=update_data)
            tasks[i] = updated_task
            return updated_task
    raise HTTPException(status_code=404, detail="Task not found")


# TODO: DELETE /tasks/{task_id} — delete a task (requires auth, 404 if not found)
@app.delete("/tasks/{task_id}")
async def delete_task(task_id: int, username: str = Depends(require_api_key)):
    for i, task in enumerate(tasks):
        if task.id == task_id:
            tasks.pop(i)
            return {"detail": "Task deleted"}
    raise HTTPException(status_code=404, detail="Task not found")
