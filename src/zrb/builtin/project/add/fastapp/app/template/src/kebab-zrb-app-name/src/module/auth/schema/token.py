from pydantic import BaseModel


class AccessTokenData(BaseModel):
    user_id: str
    username: str
    expire_seconds: int | float


class RefreshTokenData(BaseModel):
    user_id: str
    expire_seconds: int | float


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
