from typing import List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()


class TodoItem(BaseModel):
    id: int
    title: str
    completed: bool = False


class TodoCreate(BaseModel):
    title: str
    completed: bool = False


class TodoUpdate(BaseModel):
    title: Optional[str] = None
    completed: Optional[bool] = None


# In-memory database
db: List[TodoItem] = [
    TodoItem(id=1, title="Buy groceries"),
    TodoItem(id=2, title="Walk the dog"),
]


def get_next_id() -> int:
    """Generate the next ID by finding the maximum current ID and adding 1."""
    if not db:
        return 1
    return max(item.id for item in db) + 1


@app.get("/todos", response_model=List[TodoItem])
async def get_todos():
    return db


@app.post("/todos", response_model=TodoItem)
async def create_todo(todo: TodoCreate):
    """Create a new todo item with auto-generated ID."""
    new_id = get_next_id()
    new_todo = TodoItem(id=new_id, title=todo.title, completed=todo.completed)
    db.append(new_todo)
    return new_todo


@app.put("/todos/{item_id}", response_model=TodoItem)
async def update_todo(item_id: int, todo_update: TodoUpdate):
    """Update an existing todo item's title or completed status."""
    # Find the todo item
    for i, item in enumerate(db):
        if item.id == item_id:
            # Update title if provided
            if todo_update.title is not None:
                item.title = todo_update.title
            # Update completed status if provided
            if todo_update.completed is not None:
                item.completed = todo_update.completed
            return item

    # If item not found, raise 404
    raise HTTPException(
        status_code=404, detail=f"Todo item with id {item_id} not found"
    )


@app.delete("/todos/{item_id}")
async def delete_todo(item_id: int):
    """Delete a todo item by ID."""
    # Find the todo item
    for i, item in enumerate(db):
        if item.id == item_id:
            deleted_item = db.pop(i)
            return {
                "message": f"Todo item with id {item_id} deleted",
                "deleted_item": deleted_item,
            }

    # If item not found, raise 404
    raise HTTPException(
        status_code=404, detail=f"Todo item with id {item_id} not found"
    )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
