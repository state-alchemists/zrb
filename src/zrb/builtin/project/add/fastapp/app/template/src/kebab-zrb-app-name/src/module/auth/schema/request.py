from pydantic import BaseModel


class RefreshTokenRequest(BaseModel):
    access_token: str


class IsAuthorizedRequest(BaseModel):
    permission_names: list[str]
