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


@app.post("/todos", response_model=TodoItem, status_code=201)
async def create_todo(todo: TodoCreate):
    new_id = max((item.id for item in db), default=0) + 1
    new_todo = TodoItem(id=new_id, title=todo.title, completed=todo.completed)
    db.append(new_todo)
    return new_todo


@app.put("/todos/{todo_id}", response_model=TodoItem)
async def update_todo(todo_id: int, todo: TodoUpdate):
    for index, item in enumerate(db):
        if item.id == todo_id:
            updated_item = TodoItem(
                id=todo_id,
                title=todo.title if todo.title is not None else item.title,
                completed=todo.completed if todo.completed is not None else item.completed
            )
            db[index] = updated_item
            return updated_item
    raise HTTPException(status_code=404, detail="Todo not found")


@app.delete("/todos/{todo_id}", status_code=204)
async def delete_todo(todo_id: int):
    for index, item in enumerate(db):
        if item.id == todo_id:
            db.pop(index)
            return
    raise HTTPException(status_code=404, detail="Todo not found")
