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


# TODO: Implement POST /todos to add a new item
# TODO: Implement PUT /todos/{item_id} to update an item
# TODO: Implement DELETE /todos/{item_id} to delete an item

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
