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


@app.post("/todos", response_model=TodoItem, status_code=201)
async def create_todo(todo: TodoItem):
    # Auto-increment ID
    new_id = max((item.id for item in db), default=0) + 1
    new_todo = TodoItem(id=new_id, title=todo.title, completed=todo.completed)
    db.append(new_todo)
    return new_todo


@app.put("/todos/{item_id}", response_model=TodoItem)
async def update_todo(item_id: int, todo: TodoItem):
    for idx, existing_todo in enumerate(db):
        if existing_todo.id == item_id:
            updated_todo = TodoItem(
                id=item_id, title=todo.title, completed=todo.completed
            )
            db[idx] = updated_todo
            return updated_todo
    raise HTTPException(status_code=404, detail="Todo not found")


@app.delete("/todos/{item_id}", status_code=204)
async def delete_todo(item_id: int):
    for idx, existing_todo in enumerate(db):
        if existing_todo.id == item_id:
            db.pop(idx)
            return
    raise HTTPException(status_code=404, detail="Todo not found")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
