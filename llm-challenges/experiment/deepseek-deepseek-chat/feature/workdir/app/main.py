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
    page_size: int = 20
):
    filtered_tasks = tasks
    
    if status is not None:
        filtered_tasks = [task for task in filtered_tasks if task.status == status]
    
    if priority is not None:
        filtered_tasks = [task for task in filtered_tasks if task.priority == priority]
    
    if assigned_to is not None:
        filtered_tasks = [task for task in filtered_tasks if task.assigned_to == assigned_to]
    
    # Apply pagination
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    return filtered_tasks[start_idx:end_idx]


@app.get("/tasks/{task_id}", response_model=Task)
async def get_task(task_id: int):
    for task in tasks:
        if task.id == task_id:
            return task
    raise HTTPException(status_code=404, detail="Task not found")


@app.post("/tasks", response_model=Task)
async def create_task(
    task_data: TaskCreate,
    username: str = Depends(require_api_key)
):
    # Validate project_id exists
    project_exists = any(project.id == task_data.project_id for project in projects)
    if not project_exists:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Auto-generate unique ID
    if tasks:
        new_id = max(task.id for task in tasks) + 1
    else:
        new_id = 1
    
    # Create new task
    new_task = Task(
        id=new_id,
        title=task_data.title,
        status=task_data.status,
        priority=task_data.priority,
        project_id=task_data.project_id,
        assigned_to=task_data.assigned_to
    )
    
    tasks.append(new_task)
    return new_task


@app.put("/tasks/{task_id}", response_model=Task)
async def update_task(
    task_id: int,
    task_update: TaskUpdate,
    username: str = Depends(require_api_key)
):
    # Find the task
    for i, task in enumerate(tasks):
        if task.id == task_id:
            # Update only provided fields
            update_data = task_update.model_dump(exclude_unset=True)
            
            if "title" in update_data and update_data["title"] is not None:
                tasks[i].title = update_data["title"]
            
            if "status" in update_data and update_data["status"] is not None:
                tasks[i].status = update_data["status"]
            
            if "priority" in update_data and update_data["priority"] is not None:
                tasks[i].priority = update_data["priority"]
            
            if "assigned_to" in update_data:
                tasks[i].assigned_to = update_data["assigned_to"]  # Can be None to unassign
            
            return tasks[i]
    
    raise HTTPException(status_code=404, detail="Task not found")


@app.delete("/tasks/{task_id}")
async def delete_task(
    task_id: int,
    username: str = Depends(require_api_key)
):
    # Find the task
    for i, task in enumerate(tasks):
        if task.id == task_id:
            deleted_task = tasks.pop(i)
            return {"message": f"Task {task_id} deleted", "task": deleted_task}
    
    raise HTTPException(status_code=404, detail="Task not found")
