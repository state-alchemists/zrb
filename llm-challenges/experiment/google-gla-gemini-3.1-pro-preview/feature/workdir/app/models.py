from pydantic import BaseModel

class TodoCreate(BaseModel):
    title: str
    completed: bool = False

class TodoItem(TodoCreate):
    id: int
