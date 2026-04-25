from pydantic import BaseModel
from typing import Optional
from enum import Enum


class TaskStatus(str, Enum):
    todo = "todo"
    in_progress = "in_progress"
    done = "done"


class Task(BaseModel):
    id: int
    title: str
    status: TaskStatus = TaskStatus.todo
    priority: int = 3
    project_id: int
    assigned_to: Optional[str] = None


class TaskCreate(BaseModel):
    title: str
    status: TaskStatus = TaskStatus.todo
    priority: int = 3
    project_id: int
    assigned_to: Optional[str] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    status: Optional[TaskStatus] = None
    priority: Optional[int] = None
    assigned_to: Optional[str] = None


class Project(BaseModel):
    id: int
    name: str
    owner: str
