from typing import List, Optional
from pydantic import BaseModel
import datetime


class PermissionData(BaseModel):
    name: str
    description: str
    created_at: Optional[datetime.datetime]
    created_by: Optional[str]
    updated_at: Optional[datetime.datetime]
    updated_by: Optional[str]


class Permission(PermissionData):
    id: str

    class Config:
        orm_mode = True


class PermissionResult(BaseModel):
    count: int
    data: List[Permission]
