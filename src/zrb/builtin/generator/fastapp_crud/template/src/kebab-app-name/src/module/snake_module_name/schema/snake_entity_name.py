from typing import List
from core.schema import BaseDateTimeSchema, BaseCountSchema


class PascalEntityNameData(BaseDateTimeSchema):
    snake_column_name: str


class PascalEntityName(PascalEntityNameData):
    id: str

    class Config:
        orm_mode = True


class PascalEntityNameResult(BaseCountSchema):
    data: List[PascalEntityName]
