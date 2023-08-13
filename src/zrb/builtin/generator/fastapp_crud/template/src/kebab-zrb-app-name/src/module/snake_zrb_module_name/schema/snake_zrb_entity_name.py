from typing import List
from core.schema import BaseDateTimeSchema, BaseCountSchema


class PascalZrbEntityNameData(BaseDateTimeSchema):
    snake_zrb_column_name: str


class PascalZrbEntityName(PascalZrbEntityNameData):
    id: str

    class Config:
        orm_mode = True


class PascalZrbEntityNameResult(BaseCountSchema):
    data: List[PascalZrbEntityName]
