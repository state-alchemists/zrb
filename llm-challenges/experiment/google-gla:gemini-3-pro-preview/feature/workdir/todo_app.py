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


@app.post("/todos", response_model=TodoItem, status_code=201)
async def create_todo(todo: TodoCreate):
    new_id = 1
    if db:
        new_id = max(item.id for item in db) + 1
    new_item = TodoItem(id=new_id, **todo.dict())
    db.append(new_item)
    return new_item


@app.put("/todos/{item_id}", response_model=TodoItem)
async def update_todo(item_id: int, todo_update: TodoUpdate):
    for i, item in enumerate(db):
        if item.id == item_id:
            # Create a new item with updated fields
            update_data = todo_update.dict(exclude_unset=True)
            updated_item = item.copy(update=update_data)
            db[i] = updated_item
            return updated_item
    raise HTTPException(status_code=404, detail="Todo not found")


@app.delete("/todos/{item_id}", status_code=204)
async def delete_todo(item_id: int):
    for i, item in enumerate(db):
        if item.id == item_id:
            db.pop(i)
            return
    raise HTTPException(status_code=404, detail="Todo not found")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
