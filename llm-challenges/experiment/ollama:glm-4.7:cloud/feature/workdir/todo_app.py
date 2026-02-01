from typing import List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()


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


# In-memory database
db: List[TodoItem] = [
    TodoItem(id=1, title="Buy groceries"),
    TodoItem(id=2, title="Walk the dog"),
]


def get_next_id() -> int:
    return max(item.id for item in db) + 1 if db else 1


def find_todo(item_id: int) -> Optional[TodoItem]:
    return next((item for item in db if item.id == item_id), None)


@app.get("/todos", response_model=List[TodoItem])
async def get_todos():
    return db


@app.post("/todos", response_model=TodoItem, status_code=201)
async def create_todo(todo_data: TodoCreate):
    new_id = get_next_id()
    new_todo = TodoItem(id=new_id, title=todo_data.title, completed=todo_data.completed)
    db.append(new_todo)
    return new_todo


@app.put("/todos/{item_id}", response_model=TodoItem)
async def update_todo(item_id: int, todo_data: TodoUpdate):
    todo = find_todo(item_id)
    if not todo:
        raise HTTPException(status_code=404, detail="Todo item not found")
    
    if todo_data.title is not None:
        todo.title = todo_data.title
    if todo_data.completed is not None:
        todo.completed = todo_data.completed
    
    return todo


@app.delete("/todos/{item_id}", status_code=204)
async def delete_todo(item_id: int):
    todo = find_todo(item_id)
    if not todo:
        raise HTTPException(status_code=404, detail="Todo item not found")
    
    db.remove(todo)
    return None


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)