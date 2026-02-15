from fastapi import FastAPI, HTTPException
from typing import List
from .models import TodoItem, TodoCreate, TodoUpdate
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
async def create_todo(todo: TodoCreate):
    new_id = max([item.id for item in db], default=0) + 1
    new_item = TodoItem(id=new_id, title=todo.title, completed=todo.completed)
    db.append(new_item)
    return new_item

@app.put("/todos/{todo_id}", response_model=TodoItem)
async def update_todo(todo_id: int, todo_update: TodoUpdate):
    for item in db:
        if item.id == todo_id:
            if todo_update.title is not None:
                item.title = todo_update.title
            if todo_update.completed is not None:
                item.completed = todo_update.completed
            return item
    raise HTTPException(status_code=404, detail="Todo not found")

@app.delete("/todos/{todo_id}")
async def delete_todo(todo_id: int):
    for i, item in enumerate(db):
        if item.id == todo_id:
            db.pop(i)
            return {"detail": "Todo deleted"}
    raise HTTPException(status_code=404, detail="Todo not found")
