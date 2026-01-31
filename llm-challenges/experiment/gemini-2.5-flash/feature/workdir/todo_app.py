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


@app.get("/todos", response_model=List[TodoItem])
async def get_todos():
    return db


@app.post("/todos", response_model=TodoItem, status_code=201)
async def create_todo(item: TodoItemCreate):
    max_id = 0
    if db:
        max_id = max(todo.id for todo in db)
    new_id = max_id + 1
    new_todo = TodoItem(id=new_id, title=item.title, completed=item.completed)
    db.append(new_todo)
    return new_todo


@app.put("/todos/{item_id}", response_model=TodoItem)
async def update_todo(item_id: int, item: TodoItemUpdate):
    for index, todo in enumerate(db):
        if todo.id == item_id:
            if item.title is not None:
                db[index].title = item.title
            if item.completed is not None:
                db[index].completed = item.completed
            return db[index]
    raise HTTPException(status_code=404, detail="Todo item not found")


@app.delete("/todos/{item_id}", status_code=204)
async def delete_todo(item_id: int):
    for index, todo in enumerate(db):
        if todo.id == item_id:
            del db[index]
            return {"message": "Todo item deleted successfully"}
    raise HTTPException(status_code=404, detail="Todo item not found")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
