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

# TODO: Implement POST /todos
# TODO: Implement PUT /todos/{todo_id}
# TODO: Implement DELETE /todos/{todo_id}
# Note: Ensure you handle auto-incrementing IDs properly.
