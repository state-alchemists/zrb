from fastapi import FastAPI, HTTPException, Depends
from typing import List, Optional
from .models import Task, TaskCreate, TaskUpdate, Project
from .database import tasks, projects
from .auth import require_api_key

app = FastAPI(title="Project Management API")


def _project_exists(project_id: int) -> bool:
    return any(p.id == project_id for p in projects)


def _find_task(task_id: int) -> Optional[Task]:
    for task in tasks:
        if task.id == task_id:
            return task
    return None


def _tasks_with_filters(
    status: Optional[str] = None,
    priority: Optional[int] = None,
    assigned_to: Optional[str] = None,
) -> List[Task]:
    filtered = tasks
    if status is not None:
        filtered = [t for t in filtered if t.status.value == status]
    if priority is not None:
        filtered = [t for t in filtered if t.priority == priority]
    if assigned_to is not None:
        filtered = [t for t in filtered if t.assigned_to == assigned_to]
    return filtered


def _paginate(items: List[Task], page: int, page_size: int) -> List[Task]:
    start = (page - 1) * page_size
    end = start + page_size
    return items[start:end]


@app.get("/projects", response_model=List[Project])
async def list_projects():
    return projects


@app.get("/tasks", response_model=List[Task])
async def list_tasks(
    status: Optional[str] = None,
    priority: Optional[int] = None,
    assigned_to: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
):
    filtered = _tasks_with_filters(status, priority, assigned_to)
    return _paginate(filtered, page, page_size)


@app.get("/tasks/{task_id}", response_model=Task)
async def get_task(task_id: int):
    task = _find_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.post("/tasks", response_model=Task, status_code=201)
async def create_task(
    task_data: TaskCreate,
    _user: str = Depends(require_api_key),
):
    if not _project_exists(task_data.project_id):
        raise HTTPException(status_code=404, detail="Project not found")

    new_id = max((t.id for t in tasks), default=0) + 1
    task = Task(
        id=new_id,
        title=task_data.title,
        status=task_data.status,
        priority=task_data.priority,
        project_id=task_data.project_id,
        assigned_to=task_data.assigned_to,
    )
    tasks.append(task)
    return task


@app.put("/tasks/{task_id}", response_model=Task)
async def update_task(
    task_id: int,
    task_data: TaskUpdate,
    _user: str = Depends(require_api_key),
):
    task = _find_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    update_fields = task_data.model_dump(exclude_unset=True)
    for field, value in update_fields.items():
        setattr(task, field, value)
    return task


@app.delete("/tasks/{task_id}", status_code=204)
async def delete_task(
    task_id: int,
    _user: str = Depends(require_api_key),
):
    task = _find_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    tasks.remove(task)
