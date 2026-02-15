from pydantic import BaseModel
from typing import Optional

class TodoItem(BaseModel):
    id: int
    title: str
    completed: bool = False

class TodoCreate(BaseModel):
    title: str
    completed: bool = False

class TodoUpdate(BaseModel):
    title: Optional[str] = None
    completed: Optional[bool] = None
