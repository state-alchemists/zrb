Complete the FastAPI application in `resources/todo_app.py`.
1. Implement the `POST /todos` endpoint to create a new todo item. It should handle ID generation automatically (e.g., max_id + 1).
2. Implement the `PUT /todos/{item_id}` endpoint to update the `title` or `completed` status. It should return 404 if the item doesn't exist.
3. Implement the `DELETE /todos/{item_id}` endpoint.