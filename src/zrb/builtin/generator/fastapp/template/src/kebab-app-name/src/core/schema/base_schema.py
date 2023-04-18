from typing import Optional
from pydantic import BaseModel
import datetime


class BaseDateTimeSchema(BaseModel):
    created_at: Optional[datetime.datetime]
    created_by: Optional[str]
    updated_at: Optional[datetime.datetime]
    updated_by: Optional[str]


class BaseCountSchema(BaseModel):
    count: int
