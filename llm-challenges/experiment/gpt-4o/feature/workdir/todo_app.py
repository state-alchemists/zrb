from typing import List

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()


class TodoItem(BaseModel):
    id: int
    title: str
    completed: bool = False


class TodoItemCreate(BaseModel):
    title: str
    completed: bool = False


def get_next_id() -> int:
    if db:
        return max(item.id for item in db) + 1
    return 1


# In-memory database
db: List[TodoItem] = [
    TodoItem(id=1, title="Buy groceries"),
    TodoItem(id=2, title="Walk the dog"),
]


@app.get("/todos", response_model=List[TodoItem])
async def get_todos():
    return db


@app.post("/todos", response_model=TodoItem, status_code=201)
async def create_todo(todo: TodoItemCreate):
    new_todo = TodoItem(id=get_next_id(), title=todo.title, completed=todo.completed)
    db.append(new_todo)
    return new_todo


@app.put("/todos/{item_id}", response_model=TodoItem)
async def update_todo(item_id: int, todo: TodoItemCreate):
    for item in db:
        if item.id == item_id:
            item.title = todo.title
            item.completed = todo.completed
            return item
    raise HTTPException(status_code=404, detail="Todo item not found")


@app.delete("/todos/{item_id}", status_code=204)
async def delete_todo(item_id: int):
    for index, item in enumerate(db):
        if item.id == item_id:
            db.pop(index)
            return
    raise HTTPException(status_code=404, detail="Todo item not found")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
