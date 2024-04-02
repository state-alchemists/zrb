from typing import List, Optional

from component.schema import BaseCountSchema, BaseDateTimeSchema


class PascalZrbEntityNameData(BaseDateTimeSchema):
    snake_zrb_column_name: str


class PascalZrbEntityName(PascalZrbEntityNameData):
    id: str

    class Config:
        from_attributes = True


class PascalZrbEntityNameResult(BaseCountSchema):
    data: List[PascalZrbEntityName]
