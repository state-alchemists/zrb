from typing import List
from pydantic import BaseModel


class RefreshTokenRequest(BaseModel):
    token: str


class IsAuthorizedRequest(BaseModel):
    permission_names: List[str]
