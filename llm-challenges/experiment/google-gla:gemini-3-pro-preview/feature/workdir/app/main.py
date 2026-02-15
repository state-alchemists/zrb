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
async def create_todo(todo_in: TodoCreate):
    new_id = 1
    if db:
        new_id = max(item.id for item in db) + 1
    
    new_todo = TodoItem(
        id=new_id,
        title=todo_in.title,
        completed=todo_in.completed
    )
    db.append(new_todo)
    return new_todo

@app.put("/todos/{todo_id}", response_model=TodoItem)
async def update_todo(todo_id: int, todo_in: TodoUpdate):
    for item in db:
        if item.id == todo_id:
            if todo_in.title is not None:
                item.title = todo_in.title
            if todo_in.completed is not None:
                item.completed = todo_in.completed
            return item
    raise HTTPException(status_code=404, detail="Todo not found")

@app.delete("/todos/{todo_id}")
async def delete_todo(todo_id: int):
    for index, item in enumerate(db):
        if item.id == todo_id:
            del db[index]
            return {"ok": True}
    raise HTTPException(status_code=404, detail="Todo not found")
