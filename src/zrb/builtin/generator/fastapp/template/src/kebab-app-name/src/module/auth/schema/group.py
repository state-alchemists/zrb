from typing import List, Optional
from pydantic import BaseModel
import datetime


class GroupData(BaseModel):
    name: str
    description: str
    permission_ids: List[str]
    created_at: Optional[datetime.datetime]
    created_by: Optional[str]
    updated_at: Optional[datetime.datetime]
    updated_by: Optional[str]


class Group(GroupData):
    id: str

    class Config:
        orm_mode = True


class GroupResult(BaseModel):
    count: int
    data: List[Group]
