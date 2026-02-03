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


# In-memory database
db: List[TodoItem] = [
    TodoItem(id=1, title="Buy groceries"),
    TodoItem(id=2, title="Walk the dog"),
]
next_id = 3


@app.get("/todos", response_model=List[TodoItem])
async def get_todos():
    return db


@app.post("/todos", response_model=TodoItem, status_code=201)
async def create_todo(todo: TodoCreate):
    global next_id
    new_todo = TodoItem(id=next_id, title=todo.title, completed=todo.completed)
    db.append(new_todo)
    next_id += 1
    return new_todo


@app.put("/todos/{item_id}", response_model=TodoItem)
async def update_todo(item_id: int, todo: TodoCreate):
    for index, item in enumerate(db):
        if item.id == item_id:
            db[index].title = todo.title
            db[index].completed = todo.completed
            return db[index]
    raise HTTPException(status_code=404, detail="Todo item not found")


@app.delete("/todos/{item_id}", status_code=204)
async def delete_todo(item_id: int):
    global db
    initial_len = len(db)
    db = [item for item in db if item.id != item_id]
    if len(db) == initial_len:
        raise HTTPException(status_code=404, detail="Todo item not found")
    return {"message": "Todo item deleted"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
