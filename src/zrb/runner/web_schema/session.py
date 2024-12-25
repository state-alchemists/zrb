from pydantic import BaseModel


class NewSessionResponse(BaseModel):
    session_name: str
