from pydantic import BaseModel


class BasicResponse(BaseModel):
    message: str
