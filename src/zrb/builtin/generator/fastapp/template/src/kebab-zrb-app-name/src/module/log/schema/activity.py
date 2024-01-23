from typing import List

from core.schema import BaseCountSchema, BaseDateTimeSchema


class ActivityData(BaseDateTimeSchema):
    action: str
    entity: str
    data: str


class Activity(ActivityData):
    id: str

    class Config:
        orm_mode = True
        from_attributes = True


class ActivityResult(BaseCountSchema):
    data: List[Activity]
