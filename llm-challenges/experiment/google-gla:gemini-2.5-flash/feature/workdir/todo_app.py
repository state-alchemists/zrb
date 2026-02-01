from typing import List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()


class TodoItem(BaseModel):
    id: int
    title: str
    completed: bool = False

class TodoItemCreate(BaseModel):
    title: str
    completed: bool = False

class TodoItemUpdate(BaseModel):
    title: Optional[str] = None
    completed: Optional[bool] = None


# In-memory database
db: List[TodoItem] = [
    TodoItem(id=1, title="Buy groceries"),
    TodoItem(id=2, title="Walk the dog"),
]
next_id: int = 3


@app.get("/todos", response_model=List[TodoItem])
async def get_todos():
    return db


@app.get("/todos/{item_id}", response_model=TodoItem)
async def get_todo(item_id: int):
    for todo in db:
        if todo.id == item_id:
            return todo
    raise HTTPException(status_code=404, detail="Todo item not found")


@app.post("/todos", response_model=TodoItem, status_code=201)
async def create_todo(item: TodoItemCreate):
    global next_id
    new_item = TodoItem(id=next_id, title=item.title, completed=item.completed)
    db.append(new_item)
    next_id += 1
    return new_item


@app.put("/todos/{item_id}", response_model=TodoItem)
async def update_todo(item_id: int, item: TodoItemUpdate):
    for idx, todo in enumerate(db):
        if todo.id == item_id:
            update_data = item.dict(exclude_unset=True)
            updated_item = todo.copy(update=update_data)
            db[idx] = updated_item
            return updated_item
    raise HTTPException(status_code=404, detail="Todo item not found")


@app.delete("/todos/{item_id}", status_code=204)
async def delete_todo(item_id: int):
    global db
    initial_len = len(db)
    db = [todo for todo in db if todo.id != item_id]
    if len(db) == initial_len:
        raise HTTPException(status_code=404, detail="Todo item not found")
    return


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
