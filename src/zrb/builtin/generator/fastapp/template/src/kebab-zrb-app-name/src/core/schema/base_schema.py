import datetime
from typing import Optional

from pydantic import BaseModel


class BaseDateTimeSchema(BaseModel):
    created_at: Optional[datetime.datetime] = None
    created_by: Optional[str] = None
    updated_at: Optional[datetime.datetime] = None
    updated_by: Optional[str] = None


class BaseCountSchema(BaseModel):
    count: int
