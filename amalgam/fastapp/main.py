from typing import Union

from common.app import app
from module.gateway import route as gateway_route
from module.library import route as library_route

assert gateway_route
assert library_route


@app.get("/items/{item_id}")
def read_item(item_id: int, q: Union[str, None] = None):
    return {"item_id": item_id, "q": q}
