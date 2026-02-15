from fastapi import FastAPI, HTTPException
from typing import List
from pydantic import BaseModel
from .models import TodoItem
from .database import db

app = FastAPI(title="Modern Todo API")

# Input model for creating todos (without ID)
class TodoCreate(BaseModel):
    title: str
    completed: bool = False

# Input model for updating todos (without ID)
class TodoUpdate(BaseModel):
    title: str
    completed: bool

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
    # Generate new ID (max existing ID + 1)
    new_id = max((item.id for item in db), default=0) + 1
    # Create new todo with generated ID
    new_todo = TodoItem(id=new_id, title=todo.title, completed=todo.completed)
    db.append(new_todo)
    return new_todo

@app.put("/todos/{todo_id}", response_model=TodoItem)
async def update_todo(todo_id: int, todo_update: TodoUpdate):
    for i, item in enumerate(db):
        if item.id == todo_id:
            # Update the todo item
            updated_todo = TodoItem(
                id=todo_id, 
                title=todo_update.title, 
                completed=todo_update.completed
            )
            db[i] = updated_todo
            return updated_todo
    raise HTTPException(status_code=404, detail="Todo not found")

@app.delete("/todos/{todo_id}", status_code=204)
async def delete_todo(todo_id: int):
    for i, item in enumerate(db):
        if item.id == todo_id:
            db.pop(i)
            return
    raise HTTPException(status_code=404, detail="Todo not found")
