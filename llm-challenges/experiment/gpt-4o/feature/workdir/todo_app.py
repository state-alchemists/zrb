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
    new_id = max(item.id for item in db) + 1 if db else 1
    new_item = TodoItem(id=new_id, title=item.title, completed=item.completed)
    db.append(new_item)
    return new_item


@app.put("/todos/{item_id}", response_model=TodoItem)
async def update_todo(
    item_id: int, title: Optional[str] = None, completed: Optional[bool] = None
):
    for item in db:
        if item.id == item_id:
            if title is not None:
                item.title = title
            if completed is not None:
                item.completed = completed
            return item
    raise HTTPException(status_code=404, detail="Todo item not found")


@app.delete("/todos/{item_id}", status_code=204)
async def delete_todo(item_id: int):
    for index, item in enumerate(db):
        if item.id == item_id:
            del db[index]
            return
    raise HTTPException(status_code=404, detail="Todo item not found")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
