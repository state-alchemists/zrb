from fastapi import FastAPI, HTTPException
from typing import List
from .models import TodoItem
from .database import db

app = FastAPI(title="Modern Todo API")


def _find_todo_index(todo_id: int) -> int:
    for index, item in enumerate(db):
        if item.id == todo_id:
            return index
    raise HTTPException(status_code=404, detail="Todo not found")


@app.get("/todos", response_model=List[TodoItem])
async def list_todos():
    return db


@app.get("/todos/{todo_id}", response_model=TodoItem)
async def get_todo(todo_id: int):
    return db[_find_todo_index(todo_id)]


@app.post("/todos", response_model=TodoItem, status_code=201)
async def create_todo(todo: TodoItem):
    next_id = max((item.id for item in db), default=0) + 1
    new_todo = TodoItem(id=next_id, title=todo.title, completed=todo.completed)
    db.append(new_todo)
    return new_todo


@app.put("/todos/{todo_id}", response_model=TodoItem)
async def update_todo(todo_id: int, todo: TodoItem):
    todo_index = _find_todo_index(todo_id)
    updated_todo = TodoItem(id=todo_id, title=todo.title, completed=todo.completed)
    db[todo_index] = updated_todo
    return updated_todo


@app.delete("/todos/{todo_id}", response_model=TodoItem)
async def delete_todo(todo_id: int):
    todo_index = _find_todo_index(todo_id)
    return db.pop(todo_index)
