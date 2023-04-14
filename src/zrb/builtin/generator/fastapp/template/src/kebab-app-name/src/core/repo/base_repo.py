from typing import List, Type, TypeVar
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import select, update, delete
from sqlalchemy.exc import IntegrityError

Base = TypeVar("Base", bound=BaseModel)


class BaseRepository:
    def __init__(self, db_session: Session, model_type: Type[Base]):
        self.db_session = db_session
        self.model_type = model_type

    def get_one(self, id: str) -> Base:
        query = select(self.model_type).filter_by(id=id)
        result = self.db_session.execute(query).scalar_one_or_none()
        if result is None:
            raise ValueError("Record not found")
        return result

    def get(self, **kwargs) -> List[Base]:
        query = select(self.model_type).filter_by(**kwargs)
        result = self.db_session.execute(query).scalars()
        if result is None:
            raise ValueError("Record not found")
        return result

    def insert(self, data: Base) -> Base:
        try:
            record = self.model_type(**data.dict())
            self.db_session.add(record)
            self.db_session.commit()
            self.db_session.refresh(record)
            return record
        except IntegrityError:
            self.db_session.rollback()
            raise ValueError("Duplicate record")

    def update(self, id: str, data: Base) -> Base:
        query = update(self.model_type).where(
            self.model_type.id == id
        ).values(**data.dict())
        result = self.db_session.execute(query)
        if result.rowcount == 0:
            raise ValueError("Record not found")
        self.db_session.commit()
        return self.get(id)

    def delete(self, id: str) -> None:
        query = delete(self.model_type).where(self.model_type.id == id)
        result = self.db_session.execute(query)
        if result.rowcount == 0:
            raise ValueError("Record not found")
        self.db_session.commit()
