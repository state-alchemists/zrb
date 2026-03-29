from fastapi import FastAPI, HTTPException
from typing import List
from .models import TodoItem, TodoCreate
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

@app.post("/todos", response_model=TodoItem)
async def create_todo(item: TodoCreate):
    max_id = max((t.id for t in db), default=0)
    new_item = TodoItem(id=max_id + 1, title=item.title, completed=item.completed)
    db.append(new_item)
    return new_item

@app.put("/todos/{todo_id}", response_model=TodoItem)
async def update_todo(todo_id: int, item: TodoItem):
    for i, t in enumerate(db):
        if t.id == todo_id:
            updated = TodoItem(id=todo_id, title=item.title, completed=item.completed)
            db[i] = updated
            return updated
    raise HTTPException(status_code=404, detail="Todo not found")

@app.delete("/todos/{todo_id}")
async def delete_todo(todo_id: int):
    for i, t in enumerate(db):
        if t.id == todo_id:
            db.pop(i)
            return {"message": "Todo deleted"}
    raise HTTPException(status_code=404, detail="Todo not found")
