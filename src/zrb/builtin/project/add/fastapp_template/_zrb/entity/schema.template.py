import datetime

import ulid
from sqlmodel import Field, SQLModel


class MyEntityBase(SQLModel):
    my_column: str


class MyEntityCreate(MyEntityBase):
    pass


class MyEntityUpdate(SQLModel):
    my_column: str | None = None


class MyEntityResponse(MyEntityBase):
    id: str


class MyEntity(SQLModel, table=True):
    id: str = Field(default_factory=lambda: ulid.new().str, primary_key=True)
    created_at: datetime.datetime
    created_by: str
    updated_at: datetime.datetime
    updated_by: str
    my_column: str
