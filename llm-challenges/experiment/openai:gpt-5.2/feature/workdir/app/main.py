from fastapi import FastAPI, HTTPException
from typing import List
from .models import TodoItem
from .database import db

app = FastAPI(title="Modern Todo API")

@app.get("/todos", response_model=List[TodoItem])
async def list_todos():
    return db

@app.get("/todos/{todo_id}", response_model=TodoItem)
async def get_todo(todo_id: int):
    for item in db:
        if item.id == todo_id:
            return item
    raise HTTPException(status_code=404, detail="Todo not found")

@app.post("/todos", response_model=TodoItem, status_code=201)
async def create_todo(todo: TodoItem):
    # Auto-generate ID (ignore any client-provided value)
    next_id = max((item.id for item in db), default=0) + 1
    new_item = TodoItem(id=next_id, title=todo.title, completed=todo.completed)
    db.append(new_item)
    return new_item

@app.put("/todos/{todo_id}", response_model=TodoItem)
async def update_todo(todo_id: int, todo: TodoItem):
    for idx, item in enumerate(db):
        if item.id == todo_id:
            updated = TodoItem(id=todo_id, title=todo.title, completed=todo.completed)
            db[idx] = updated
            return updated
    raise HTTPException(status_code=404, detail="Todo not found")

@app.delete("/todos/{todo_id}", status_code=204)
async def delete_todo(todo_id: int):
    for idx, item in enumerate(db):
        if item.id == todo_id:
            db.pop(idx)
            return
    raise HTTPException(status_code=404, detail="Todo not found")
