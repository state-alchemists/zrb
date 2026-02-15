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
@app.post("/todos", response_model=TodoItem)
async def add_todo(todo: TodoItem):
    # Auto-generate ID based on the last item ID
    new_id = (db[-1].id + 1) if db else 1
    new_todo = TodoItem(id=new_id, **todo.dict())
    db.append(new_todo)
    return new_todo

@app.put("/todos/{todo_id}", response_model=TodoItem)
async def update_todo(todo_id: int, todo: TodoItem):
    for index, item in enumerate(db):
        if item.id == todo_id:
            db[index] = TodoItem(id=todo_id, **todo.dict())
            return db[index]
    raise HTTPException(status_code=404, detail="Todo not found")

@app.delete("/todos/{todo_id}", response_model=TodoItem)
async def delete_todo(todo_id: int):
    for index, item in enumerate(db):
        if item.id == todo_id:
            return db.pop(index)
    raise HTTPException(status_code=404, detail="Todo not found")
