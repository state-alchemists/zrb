import datetime

import ulid
from sqlmodel import Field, SQLModel


class BookBase(SQLModel):
    title: str


class BookCreate(BookBase):
    pass


class BookUpdate(SQLModel):
    title: str | None = None


class BookResponse(BookBase):
    id: str


class Book(SQLModel, table=True):
    id: str = Field(default_factory=lambda: ulid.new().str, primary_key=True)
    created_at: datetime.datetime
    created_by: str
    updated_at: datetime.datetime
    updated_by: str
    title: str
