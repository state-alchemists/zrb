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


@app.get("/todos", response_model=List[TodoItem])
async def get_todos():
    return db


@app.post("/todos", response_model=TodoItem)
async def create_todo(todo: TodoCreate):
    # Generate new ID (max existing ID + 1)
    max_id = max(item.id for item in db) if db else 0
    new_id = max_id + 1

    # Create new todo item
    new_todo = TodoItem(id=new_id, title=todo.title, completed=todo.completed)
    db.append(new_todo)

    return new_todo


@app.put("/todos/{item_id}", response_model=TodoItem)
async def update_todo(item_id: int, todo_update: TodoUpdate):
    # Find the todo item
    for i, item in enumerate(db):
        if item.id == item_id:
            # Update fields if provided
            if todo_update.title is not None:
                item.title = todo_update.title
            if todo_update.completed is not None:
                item.completed = todo_update.completed

            # Update in database
            db[i] = item
            return item

    # Item not found
    raise HTTPException(status_code=404, detail="Todo item not found")


@app.delete("/todos/{item_id}")
async def delete_todo(item_id: int):
    # Find the todo item
    for i, item in enumerate(db):
        if item.id == item_id:
            # Remove from database
            del db[i]
            return {"message": "Todo item deleted successfully"}

    # Item not found
    raise HTTPException(status_code=404, detail="Todo item not found")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
