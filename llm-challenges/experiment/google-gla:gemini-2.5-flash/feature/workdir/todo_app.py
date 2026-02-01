from typing import List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()


class TodoItem(BaseModel):
    id: int
    title: str
    completed: bool = False


class CreateTodoItem(BaseModel):
    title: str
    completed: bool = False


# In-memory database
db: List[TodoItem] = [
    TodoItem(id=1, title="Buy groceries"),
    TodoItem(id=2, title="Walk the dog"),
]

# Simple ID counter for auto-increment
next_id = 3


@app.get("/todos", response_model=List[TodoItem])
async def get_todos():
    return db


@app.post("/todos", response_model=TodoItem, status_code=201)
async def create_todo_item(item: CreateTodoItem):
    global next_id
    new_item = TodoItem(id=next_id, title=item.title, completed=item.completed)
    db.append(new_item)
    next_id += 1
    return new_item


@app.put("/todos/{item_id}", response_model=TodoItem)
async def update_todo_item(item_id: int, updated_item: CreateTodoItem):
    for index, item in enumerate(db):
        if item.id == item_id:
            db[index].title = updated_item.title
            db[index].completed = updated_item.completed
            return db[index]
    raise HTTPException(status_code=404, detail="Todo item not found")


@app.delete("/todos/{item_id}", status_code=204)
async def delete_todo_item(item_id: int):
    global db
    initial_len = len(db)
    db = [item for item in db if item.id != item_id]
    if len(db) == initial_len:
        raise HTTPException(status_code=404, detail="Todo item not found")
    return  # No content for 204


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
