from typing import List

from component.schema import BaseCountSchema, BaseDateTimeSchema


class PascalZrbEntityNameData(BaseDateTimeSchema):
    snake_zrb_column_name: str


class PascalZrbEntityName(PascalZrbEntityNameData):
    id: str

    class Config:
        orm_mode = True
        from_attributes = True


class PascalZrbEntityNameResult(BaseCountSchema):
    data: List[PascalZrbEntityName]
