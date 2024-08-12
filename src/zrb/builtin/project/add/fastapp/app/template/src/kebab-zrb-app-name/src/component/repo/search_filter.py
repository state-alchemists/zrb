from typing import Any

from pydantic import BaseModel


class SearchFilter(BaseModel):
    keyword: str
    criterion: dict[str, Any]
