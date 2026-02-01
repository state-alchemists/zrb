from typing import List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException
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


@app.get("/todos", response_model=List[TodoItem])
async def get_todos():
    return db


# Create a new todo item
@app.post("/todos", response_model=TodoItem, status_code=201)
async def create_todo(title: str, completed: bool = False):
    # Auto-increment ID
    new_id = max(item.id for item in db) + 1 if db else 1
    new_todo = TodoItem(id=new_id, title=title, completed=completed)
    db.append(new_todo)
    return new_todo


# Update an existing todo item
@app.put("/todos/{item_id}", response_model=TodoItem)
async def update_todo(
    item_id: int, title: Optional[str] = None, completed: Optional[bool] = None
):
    # Find the item by id
    todo_item = next((item for item in db if item.id == item_id), None)

    if todo_item is None:
        raise HTTPException(status_code=404, detail="Todo item not found")

    # Update fields if provided
    if title is not None:
        todo_item.title = title
    if completed is not None:
        todo_item.completed = completed

    return todo_item


# Delete a todo item
@app.delete("/todos/{item_id}", status_code=204)
async def delete_todo(item_id: int):
    # Find and remove the item by id
    todo_index = next((i for i, item in enumerate(db) if item.id == item_id), None)

    if todo_index is None:
        raise HTTPException(status_code=404, detail="Todo item not found")

    db.pop(todo_index)
    return None


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
