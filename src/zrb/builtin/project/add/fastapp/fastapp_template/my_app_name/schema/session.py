import datetime

import ulid
from pydantic import BaseModel
from sqlmodel import Field, SQLModel


class SessionBase(SQLModel):
    user_id: str
    device: str
    os: str
    browser: str
    expired_at: datetime.datetime | None


class SessionCreate(SessionBase):
    pass


class SessionUpdate(SessionBase):
    pass


class SessionResponse(SessionBase):
    id: str
    created_at: datetime.datetime = Field(index=True)
    updated_at: datetime.datetime | None = Field(index=True)


class MultipleSessionResponse(BaseModel):
    data: list[SessionResponse]
    count: int


class Session(SQLModel, table=True):
    id: str = Field(default_factory=lambda: ulid.new().str, primary_key=True)
    user_id: str = Field(index=True)
    device: str
    os: str
    browser: str
