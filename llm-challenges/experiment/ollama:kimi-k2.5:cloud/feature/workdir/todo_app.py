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


class TodoUpdate(BaseModel):
    title: Optional[str] = None
    completed: Optional[bool] = None


def _get_next_id() -> int:
    if not db:
        return 1
    return max(item.id for item in db) + 1


@app.post("/todos", response_model=TodoItem, status_code=201)
async def create_todo(todo: TodoCreate):
    new_item = TodoItem(id=_get_next_id(), title=todo.title, completed=todo.completed)
    db.append(new_item)
    return new_item


@app.put("/todos/{item_id}", response_model=TodoItem)
async def update_todo(item_id: int, todo: TodoUpdate):
    for item in db:
        if item.id == item_id:
            if todo.title is not None:
                item.title = todo.title
            if todo.completed is not None:
                item.completed = todo.completed
            return item
    raise HTTPException(
        status_code=404, detail=f"Todo item with id {item_id} not found"
    )


@app.delete("/todos/{item_id}", status_code=204)
async def delete_todo(item_id: int):
    for index, item in enumerate(db):
        if item.id == item_id:
            db.pop(index)
            return None
    raise HTTPException(
        status_code=404, detail=f"Todo item with id {item_id} not found"
    )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
