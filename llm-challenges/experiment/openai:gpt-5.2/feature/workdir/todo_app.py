from typing import List

import uvicorn
from fastapi import FastAPI, HTTPException, Response, status
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
    title: str | None = None
    completed: bool | None = None


# In-memory database
db: List[TodoItem] = [
    TodoItem(id=1, title="Buy groceries"),
    TodoItem(id=2, title="Walk the dog"),
]

_next_id = 3


def _get_next_id() -> int:
    global _next_id
    next_id = _next_id
    _next_id += 1
    return next_id


def _find_item_index(item_id: int) -> int:
    for i, item in enumerate(db):
        if item.id == item_id:
            return i
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Todo item not found")


@app.get("/todos", response_model=List[TodoItem])
async def get_todos():
    return db


@app.post("/todos", response_model=TodoItem, status_code=status.HTTP_201_CREATED)
async def create_todo(payload: TodoItemCreate):
    item = TodoItem(id=_get_next_id(), title=payload.title, completed=payload.completed)
    db.append(item)
    return item


@app.put("/todos/{item_id}", response_model=TodoItem)
async def update_todo(item_id: int, payload: TodoItemUpdate):
    idx = _find_item_index(item_id)
    current = db[idx]
    updated = current.model_copy(
        update={
            **({"title": payload.title} if payload.title is not None else {}),
            **({"completed": payload.completed} if payload.completed is not None else {}),
        }
    )
    db[idx] = updated
    return updated


@app.delete("/todos/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_todo(item_id: int):
    idx = _find_item_index(item_id)
    db.pop(idx)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
