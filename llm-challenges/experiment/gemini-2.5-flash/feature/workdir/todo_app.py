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
next_id = 3


@app.get("/todos", response_model=List[TodoItem])
async def get_todos():
    return db


@app.post("/todos", response_model=TodoItem, status_code=201)
async def create_todo(item: TodoItem):
    global next_id
    item.id = next_id
    next_id += 1
    db.append(item)
    return item


@app.put("/todos/{item_id}", response_model=TodoItem)
async def update_todo(item_id: int, updated_item: TodoItem):
    for index, item in enumerate(db):
        if item.id == item_id:
            db[index] = updated_item
            db[index].id = item_id  # Ensure ID remains the same
            return db[index]
    raise HTTPException(status_code=404, detail="Todo item not found")


@app.delete("/todos/{item_id}", status_code=204)
async def delete_todo(item_id: int):
    global db
    initial_len = len(db)
    db = [item for item in db if item.id != item_id]
    if len(db) == initial_len:
        raise HTTPException(status_code=404, detail="Todo item not found")
    return


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
