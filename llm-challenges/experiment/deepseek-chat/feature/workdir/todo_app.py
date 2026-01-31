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


class TodoCreate(BaseModel):
    title: str
    completed: bool = False


@app.post("/todos", response_model=TodoItem, status_code=201)
async def create_todo(item: TodoCreate):
    # Generate a new ID (max existing ID + 1)
    new_id = max((todo.id for todo in db), default=0) + 1
    new_item = TodoItem(id=new_id, title=item.title, completed=item.completed)
    db.append(new_item)
    return new_item


@app.put("/todos/{item_id}", response_model=TodoItem)
async def update_todo(item_id: int, item: TodoCreate):
    # Find the item to update
    for i, todo in enumerate(db):
        if todo.id == item_id:
            updated_item = TodoItem(
                id=item_id, title=item.title, completed=item.completed
            )
            db[i] = updated_item
            return updated_item

    # Item not found
    raise HTTPException(status_code=404, detail="Todo item not found")


@app.delete("/todos/{item_id}", status_code=204)
async def delete_todo(item_id: int):
    # Find and remove the item
    for i, todo in enumerate(db):
        if todo.id == item_id:
            db.pop(i)
            return

    # Item not found
    raise HTTPException(status_code=404, detail="Todo item not found")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
