from typing import List
from core.schema import BaseDateTimeSchema, BaseCountSchema


class ActivityData(BaseDateTimeSchema):
    action: str
    entity: str
    data: str


class Activity(ActivityData):
    id: str

    class Config:
        orm_mode = True


class ActivityResult(BaseCountSchema):
    data: List[Activity]
