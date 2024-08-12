from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel


class SearchFilter(BaseModel):
    keyword: str
    criterion: Mapping[str, Any]
