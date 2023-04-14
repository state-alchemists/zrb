from typing import List
from pydantic import BaseModel


class TokenData(BaseModel):
    user_id: str
    permissions: List[str]
    expire_seconds: int
