from typing import List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()


class TodoItem(BaseModel):
    id: int
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
async def create_todo(todo: TodoItem):
    # Auto-increment ID based on max existing ID
    if db:
        todo.id = max(item.id for item in db) + 1
    else:
        todo.id = 1
    db.append(todo)
    return todo


@app.put("/todos/{item_id}", response_model=TodoItem)
async def update_todo(item_id: int, updated_todo: TodoItem):
    for i, item in enumerate(db):
        if item.id == item_id:
            updated_todo.id = item_id
            db[i] = updated_todo
            return updated_todo
    raise HTTPException(status_code=404, detail="Todo item not found")


@app.delete("/todos/{item_id}", status_code=200)
async def delete_todo(item_id: int):
    for i, item in enumerate(db):
        if item.id == item_id:
            db.pop(i)
            return {"message": "Todo item deleted successfully"}
    raise HTTPException(status_code=404, detail="Todo item not found")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
