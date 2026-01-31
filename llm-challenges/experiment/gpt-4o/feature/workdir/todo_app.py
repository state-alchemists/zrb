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


@app.post("/todos", response_model=TodoItem)
async def create_todo(item: TodoItem):
    # Calculate ID
    item.id = max((todo.id for todo in db), default=0) + 1
    db.append(item)
    return item


@app.put("/todos/{item_id}", response_model=TodoItem)
async def update_todo(item_id: int, title: Optional[str] = None, completed: Optional[bool] = None):
    for todo in db:
        if todo.id == item_id:
            if title is not None:
                todo.title = title
            if completed is not None:
                todo.completed = completed
            return todo
    raise HTTPException(status_code=404, detail="Item not found")


@app.delete("/todos/{item_id}")
async def delete_todo(item_id: int):
    global db
    db = [todo for todo in db if todo.id != item_id]
    return {"msg": "Item deleted"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
