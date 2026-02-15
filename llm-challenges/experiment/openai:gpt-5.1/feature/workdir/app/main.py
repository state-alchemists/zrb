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
    # Auto-increment ID based on current max ID in db
    new_id = max((item.id for item in db), default=0) + 1
    new_todo = TodoItem(id=new_id, title=todo.title, completed=todo.completed)
    db.append(new_todo)
    return new_todo

@app.put("/todos/{todo_id}", response_model=TodoItem)
async def update_todo(todo_id: int, updated: TodoItem):
    for index, item in enumerate(db):
        if item.id == todo_id:
            # Preserve the path ID as source of truth
            new_item = TodoItem(id=todo_id, title=updated.title, completed=updated.completed)
            db[index] = new_item
            return new_item
    raise HTTPException(status_code=404, detail="Todo not found")

@app.delete("/todos/{todo_id}", status_code=204)
async def delete_todo(todo_id: int):
    for index, item in enumerate(db):
        if item.id == todo_id:
            del db[index]
            return
    raise HTTPException(status_code=404, detail="Todo not found")

# TODO: Implement POST /todos
# TODO: Implement PUT /todos/{todo_id}
# TODO: Implement DELETE /todos/{todo_id}
# Note: Ensure you handle auto-incrementing IDs properly.
