from typing import Any, Mapping

from pydantic import BaseModel


class SearchFilter(BaseModel):
    keyword: str
    criterion: Mapping[str, Any]
