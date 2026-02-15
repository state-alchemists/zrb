from pydantic import BaseModel
from typing import Optional

class TodoItem(BaseModel):
    id: int
    title: str
    completed: bool = False

class TodoItemCreate(BaseModel):
    title: str

class TodoItemUpdate(BaseModel):
    title: Optional[str] = None
    completed: Optional[bool] = None
