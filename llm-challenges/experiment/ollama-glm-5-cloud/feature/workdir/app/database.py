from typing import List
from .models import TodoItem

# Shared in-memory database
db: List[TodoItem] = [
    TodoItem(id=1, title="Buy groceries"),
    TodoItem(id=2, title="Walk the dog"),
]

# Auto-increment counter starting after initial data
_id_counter = 3

def next_id() -> int:
    global _id_counter
    current = _id_counter
    _id_counter += 1
    return current
