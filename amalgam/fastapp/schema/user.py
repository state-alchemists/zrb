import datetime

import ulid
from sqlmodel import Field, SQLModel


class UserBase(SQLModel):
    username: str


class UserCreate(UserBase):
    password: str


class UserUpdate(SQLModel):
    username: str | None = None
    password: str | None = None


class UserResponse(UserBase):
    id: str


class User(SQLModel, table=True):
    id: str = Field(default_factory=lambda: ulid.new().str, primary_key=True)
    created_at: datetime.datetime
    created_by: str
    updated_at: datetime.datetime
    updated_by: str
    username: str
    password: str
