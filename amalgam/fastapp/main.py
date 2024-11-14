from typing import Union

from .common.app import app
from .module.auth import route as auth_route
from .module.gateway import route as gateway_route

assert gateway_route
assert auth_route


@app.get("/items/{item_id}")
def read_item(item_id: int, q: Union[str, None] = None):
    return {"item_id": item_id, "q": q}
