from typing import List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, status
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


@app.get("/todos", response_model=List[TodoItem])
async def get_todos():
    return db


@app.post("/todos", response_model=TodoItem, status_code=status.HTTP_201_CREATED)
async def create_todo(item: TodoCreate):
    """Create a new todo item with an auto-incremented ID."""
    # Determine next ID (auto-increment based on current max ID)
    next_id = max((todo.id for todo in db), default=0) + 1
    new_item = TodoItem(id=next_id, title=item.title, completed=item.completed)
    db.append(new_item)
    return new_item


@app.put("/todos/{item_id}", response_model=TodoItem)
async def update_todo(item_id: int, item: TodoUpdate):
    """Update an existing todo item by ID.

    All provided fields will overwrite existing values; missing fields are left unchanged.
    """
    for idx, todo in enumerate(db):
        if todo.id == item_id:
            updated_data = todo.dict()
            if item.title is not None:
                updated_data["title"] = item.title
            if item.completed is not None:
                updated_data["completed"] = item.completed
            updated_item = TodoItem(**updated_data)
            db[idx] = updated_item
            return updated_item

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="Todo item not found"
    )


@app.delete("/todos/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_todo(item_id: int):
    """Delete a todo item by ID."""
    for idx, todo in enumerate(db):
        if todo.id == item_id:
            del db[idx]
            # 204 responses should not include a body
            return

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="Todo item not found"
    )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
