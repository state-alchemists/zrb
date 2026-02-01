from typing import List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel

app = FastAPI()


class TodoItem(BaseModel):
    id: int
    title: str
    completed: bool = False


class CreateTodoItemRequest(BaseModel):
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


@app.get("/todos/{item_id}", response_model=TodoItem)
async def get_todo_by_id(item_id: int):
    for todo in db:
        if todo.id == item_id:
            return todo
    raise HTTPException(status_code=404, detail="Todo not found")


@app.post("/todos", response_model=TodoItem, status_code=status.HTTP_201_CREATED)
async def create_todo(item: CreateTodoItemRequest):
    new_id = max(t.id for t in db) + 1 if db else 1
    todo = TodoItem(id=new_id, title=item.title, completed=item.completed)
    db.append(todo)
    return todo


@app.put("/todos/{item_id}", response_model=TodoItem)
async def update_todo(item_id: int, item: CreateTodoItemRequest):
    for todo in db:
        if todo.id == item_id:
            todo.title = item.title
            todo.completed = item.completed
            return todo
    raise HTTPException(status_code=404, detail="Todo not found")


@app.delete("/todos/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_todo(item_id: int):
    for i, todo in enumerate(db):
        if todo.id == item_id:
            del db[i]
            return
    raise HTTPException(status_code=404, detail="Todo not found")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
