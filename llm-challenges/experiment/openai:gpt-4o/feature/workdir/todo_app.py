from typing import List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()


class TodoItemBase(BaseModel):
    title: str
    completed: bool = False


class TodoItem(TodoItemBase):
    id: int


# In-memory database
db: List[TodoItem] = [
    TodoItem(id=1, title="Buy groceries"),
    TodoItem(id=2, title="Walk the dog"),
]


@app.get("/todos", response_model=List[TodoItem])
async def get_todos():
    return db


@app.post("/todos", response_model=TodoItem, status_code=201)
async def create_todo(item: TodoItemBase):
    new_id = db[-1].id + 1 if db else 1
    new_item = TodoItem(id=new_id, **item.dict())
    db.append(new_item)
    return new_item


@app.put("/todos/{item_id}", response_model=TodoItem)
async def update_todo(item_id: int, item: TodoItemBase):
    for db_item in db:
        if db_item.id == item_id:
            db_item.title = item.title
            db_item.completed = item.completed
            return db_item
    raise HTTPException(status_code=404, detail="Item not found")


@app.delete("/todos/{item_id}", status_code=204)
async def delete_todo(item_id: int):
    global db
    db = [item for item in db if item.id != item_id]
    return


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
