from pydantic import BaseModel


class FrontendConfig(BaseModel):
    brand: str
    title: str
    access_token_cookie_key: str
    refresh_token_cookie_key: str
