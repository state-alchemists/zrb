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
    from fastapi import Query
    
    def filter_tasks(tasks, status: str=None, priority: int=None, assigned_to: str=None):
        return [task for task in tasks if
                (status is None or task.status == status) and
                (priority is None or task.priority == priority) and
                (assigned_to is None or task.assigned_to == assigned_to)]

    def paginate_tasks(tasks, page: int=1, page_size: int=20):
        start = (page - 1) * page_size
        end = start + page_size
        return tasks[start:end]

    status: str = Query(None)
    priority: int = Query(None)
    assigned_to: str = Query(None)
    page: int = Query(1)
    page_size: int = Query(20)

    filtered_tasks = filter_tasks(tasks, status, priority, assigned_to)
    paginated_tasks = paginate_tasks(filtered_tasks, page, page_size)
    return paginated_tasks


@app.get("/tasks/{task_id}", response_model=Task)
async def get_task(task_id: int):
    for task in tasks:
        if task.id == task_id:
            return task
    raise HTTPException(status_code=404, detail="Task not found")


from fastapi import Depends

@app.post("/tasks", response_model=Task)
async def create_task(task: TaskCreate, api_key: str = Depends(require_api_key)):
    # Validate project_id
    project_exists = any(project.id == task.project_id for project in projects)
    if not project_exists:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Auto-generate task ID
    new_id = max(task.id for task in tasks) + 1 if tasks else 1
    
    # Create and append task
    new_task = Task(id=new_id, **task.dict())
    tasks.append(new_task)
    return new_task

@app.put("/tasks/{task_id}", response_model=Task)
async def update_task(task_id: int, task_update: TaskUpdate, api_key: str = Depends(require_api_key)):
    for task in tasks:
        if task.id == task_id:
            update_data = task_update.dict(exclude_unset=True)
            for key, value in update_data.items():
                setattr(task, key, value)
            return task
    raise HTTPException(status_code=404, detail="Task not found")

@app.delete("/tasks/{task_id}", response_model=None)
async def delete_task(task_id: int, api_key: str = Depends(require_api_key)):
    for i, task in enumerate(tasks):
        if task.id == task_id:
            del tasks[i]
            return
    raise HTTPException(status_code=404, detail="Task not found")

