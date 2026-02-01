from typing import List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel

app = FastAPI()

class TodoItem(BaseModel):
    id: int
    title: str
    completed: bool = False

# In-memory database
db: List[TodoItem] = [
    TodoItem(id=1, title="Buy groceries"),
    TodoItem(id=2, title="Walk the dog"),
]

next_id = 3
class TodoItemCreate(BaseModel):
    title: str
    completed: bool = False

@app.get("/todos", response_model=List[TodoItem])
async def get_todos():
    return db

@app.post("/todos", response_model=TodoItem, status_code=201)
async def create_todo(item: TodoItemCreate):
    global next_id
    new_item = TodoItem(id=next_id, title=item.title, completed=item.completed)
    db.append(new_item)
    next_id += 1
    return new_item

@app.put("/todos/{item_id}", response_model=TodoItem)
async def update_todo(item_id: int, item: TodoItemCreate):
    for i, todo in enumerate(db):
        if todo.id == item_id:
            updated_todo = TodoItem(id=item_id, title=item.title, completed=item.completed)
            db[i] = updated_todo
            return updated_todo
    raise HTTPException(status_code=404, detail="Todo not found")

@app.delete("/todos/{item_id}", status_code=204)
async def delete_todo(item_id: int):
    for i, todo in enumerate(db):
        if todo.id == item_id:
            del db[i]
            return
    raise HTTPException(status_code=404, detail="Todo not found")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)