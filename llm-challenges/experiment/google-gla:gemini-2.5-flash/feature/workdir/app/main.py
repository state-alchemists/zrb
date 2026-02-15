from fastapi import FastAPI, HTTPException
from typing import List, Optional
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

@app.post("/todos", response_model=TodoItem, status_code=201)
async def create_todo(todo: TodoCreate):
    new_id = max([item.id for item in db]) + 1 if db else 1
    new_todo = TodoItem(id=new_id, title=todo.title, completed=todo.completed)
    db.append(new_todo)
    return new_todo

@app.put("/todos/{todo_id}", response_model=TodoItem)
async def update_todo(todo_id: int, todo: TodoUpdate):
    for idx, item in enumerate(db):
        if item.id == todo_id:
            update_data = todo.model_dump(exclude_unset=True)
            updated_item = item.model_copy(update=update_data)
            db[idx] = updated_item
            return updated_item
    raise HTTPException(status_code=404, detail="Todo not found")

@app.delete("/todos/{todo_id}", status_code=204)
async def delete_todo(todo_id: int):
    for idx, item in enumerate(db):
        if item.id == todo_id:
            del db[idx]
            return # FastAPI will return 204 No Content for a successful delete.
    raise HTTPException(status_code=404, detail="Todo not found")
