from typing import List, Optional
from pydantic import BaseModel
import datetime


class UserData(BaseModel):
    username: str
    phone: str
    email: str
    password: str
    description: str
    permission_ids: List[str]
    group_ids: List[str]
    created_at: Optional[datetime.datetime]
    created_by: Optional[str]
    updated_at: Optional[datetime.datetime]
    updated_by: Optional[str]


class User(UserData):
    id: str

    class Config:
        orm_mode = True


class UserResult(BaseModel):
    count: int
    data: List[User]
