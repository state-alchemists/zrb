from typing import List
from pydantic import BaseModel


class TokenData(BaseModel):
    user_id: str
    username: str
    permissions: List[str]
    expire_seconds: int


class TokenResponse(BaseModel):
    token: str
