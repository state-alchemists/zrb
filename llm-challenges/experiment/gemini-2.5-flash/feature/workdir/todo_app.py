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
    max_id = 0
    if db:
        max_id = max(item.id for item in db)
    new_id = max_id + 1
    new_item = TodoItem(id=new_id, title=todo.title, completed=todo.completed)
    db.append(new_item)
    return new_item


@app.put("/todos/{item_id}", response_model=TodoItem)
async def update_todo(item_id: int, todo_update: TodoUpdate):
    for index, item in enumerate(db):
        if item.id == item_id:
            if todo_update.title is not None:
                db[index].title = todo_update.title
            if todo_update.completed is not None:
                db[index].completed = todo_update.completed
            return db[index]
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
