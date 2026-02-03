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
    title: str
    completed: bool = False


# In-memory database
db: List[TodoItem] = [
    TodoItem(id=1, title="Buy groceries"),
    TodoItem(id=2, title="Walk the dog"),
]


@app.get("/todos", response_model=List[TodoItem])
async def get_todos():
    return db


@app.post("/todos", response_model=TodoItem, status_code=201)
async def create_todo(todo: TodoCreate):
    next_id = max((item.id for item in db), default=0) + 1
    new_item = TodoItem(id=next_id, title=todo.title, completed=todo.completed)
    db.append(new_item)
    return new_item


@app.put("/todos/{item_id}", response_model=TodoItem)
async def update_todo(item_id: int, todo: TodoUpdate):
    for item in db:
        if item.id == item_id:
            item.title = todo.title
            item.completed = todo.completed
            return item
    raise HTTPException(status_code=404, detail="Item not found")


@app.delete("/todos/{item_id}", status_code=204)
async def delete_todo(item_id: int):
    for idx, item in enumerate(db):
        if item.id == item_id:
            del db[idx]
            return
    raise HTTPException(status_code=404, detail="Item not found")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
