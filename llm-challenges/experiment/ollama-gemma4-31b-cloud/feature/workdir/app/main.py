from fastapi import FastAPI, HTTPException, Depends
from typing import List, Optional
from .models import Task, TaskCreate, TaskUpdate, Project
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


# TODO: POST /tasks — create a task (requires auth, validate project_id, auto-generate id)
# TODO: PUT /tasks/{task_id} — partial update (requires auth, 404 if not found)
# TODO: DELETE /tasks/{task_id} — delete a task (requires auth, 404 if not found)

@app.post("/tasks", response_model=Task)
async def create_task(task_data: TaskCreate, user: str = Depends(require_api_key)):
    if not any(p.id == task_data.project_id for p in projects):
        raise HTTPException(status_code=404, detail="Project not found")
    
    new_id = max([t.id for t in tasks], default=0) + 1
    new_task = Task(id=new_id, **task_data.model_dump())
    tasks.append(new_task)
    return new_task

@app.put("/tasks/{task_id}", response_model=Task)
async def update_task(task_id: int, update_data: TaskUpdate, user: str = Depends(require_api_key)):
    for task in tasks:
        if task.id == task_id:
            update_dict = update_data.model_dump(exclude_unset=True)
            for key, value in update_dict.items():
                setattr(task, key, value)
            return task
    raise HTTPException(status_code=404, detail="Task not found")

@app.delete("/tasks/{task_id}")
async def delete_task(task_id: int, user: str = Depends(require_api_key)):
    for i, task in enumerate(tasks):
        if task.id == task_id:
            tasks.pop(i)
            return {"detail": "Task deleted"}
    raise HTTPException(status_code=404, detail="Task not found")
