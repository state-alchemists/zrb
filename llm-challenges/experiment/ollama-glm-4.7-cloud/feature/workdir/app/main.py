from fastapi import FastAPI, HTTPException, status
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

@app.post("/todos", response_model=TodoItem, status_code=status.HTTP_201_CREATED)
async def create_todo(todo: TodoCreate):
    # Generate new ID
    new_id = max((item.id for item in db), default=0) + 1
    new_todo = TodoItem(id=new_id, **todo.dict())
    db.append(new_todo)
    return new_todo

@app.put("/todos/{todo_id}", response_model=TodoItem)
async def update_todo(todo_id: int, todo: TodoCreate):
    for index, item in enumerate(db):
        if item.id == todo_id:
            db[index] = TodoItem(id=todo_id, **todo.dict())
            return db[index]
    raise HTTPException(status_code=404, detail="Todo not found")

@app.delete("/todos/{todo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_todo(todo_id: int):
    for index, item in enumerate(db):
        if item.id == todo_id:
            db.pop(index)
            return
    raise HTTPException(status_code=404, detail="Todo not found")
