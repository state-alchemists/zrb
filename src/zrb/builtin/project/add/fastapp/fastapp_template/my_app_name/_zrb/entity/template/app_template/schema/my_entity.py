import datetime

import ulid
from pydantic import BaseModel
from sqlmodel import Field, SQLModel


class MyEntityBase(SQLModel):
    my_column: str


class MyEntityCreate(MyEntityBase):
    def with_audit(self, created_by: str) -> "MyEntityCreateWithAudit":
        return MyEntityCreateWithAudit(**self.model_dump(), created_by=created_by)


class MyEntityCreateWithAudit(MyEntityCreate):
    created_by: str


class MyEntityUpdate(SQLModel):
    my_column: str | None = None

    def with_audit(self, updated_by: str) -> "MyEntityUpdateWithAudit":
        return MyEntityUpdateWithAudit(
            **self.model_dump(exclude_none=True), updated_by=updated_by
        )


class MyEntityUpdateWithAudit(MyEntityUpdate):
    updated_by: str


class MyEntityResponse(MyEntityBase):
    id: str


class MultipleMyEntityResponse(BaseModel):
    data: list[MyEntityResponse]
    count: int


class MyEntity(SQLModel, table=True):
    __tablename__ = "my_entities"
    id: str = Field(default_factory=lambda: ulid.new().str, primary_key=True)
    created_at: datetime.datetime = Field(index=True)
    created_by: str = Field(index=True)
    updated_at: datetime.datetime | None = Field(index=True)
    updated_by: str | None = Field(index=True)
    my_column: str = Field(index=True)
