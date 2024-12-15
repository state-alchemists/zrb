from typing import Any, Callable, Generic, Type, TypeVar

from fastapp_template.common.error import NotFoundError
from sqlalchemy import Engine
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlmodel import Session, SQLModel, select

DBModel = TypeVar("DBModel", bound=SQLModel)
ResponseModel = TypeVar("Model", bound=SQLModel)
CreateModel = TypeVar("CreateModel", bound=SQLModel)
UpdateModel = TypeVar("UpdateModel", bound=SQLModel)


class BaseDBRepository(Generic[DBModel, ResponseModel, CreateModel, UpdateModel]):
    db_model: Type[DBModel]
    response_model: Type[ResponseModel]
    create_model: Type[CreateModel]
    update_model: Type[UpdateModel]
    entity_name: str = "entity"
    column_preprocessors: dict[str, Callable[[Any], Any]] = {}

    def __init__(self, engine: Engine | AsyncEngine):
        self.engine = engine
        self.is_async = isinstance(engine, AsyncEngine)

    def _to_response(self, db_instance: DBModel) -> ResponseModel:
        return self.response_model(**db_instance.model_dump())

    async def create(self, data: CreateModel) -> ResponseModel:
        data_dict = data.model_dump(exclude_unset=True)
        for key, preprocessor in self.column_preprocessors.items():
            if key in data_dict:
                data_dict[key] = preprocessor(data_dict[key])
        db_instance = self.db_model(**data_dict)
        if self.is_async:
            async with AsyncSession(self.engine) as session:
                session.add(db_instance)
                await session.commit()
                await session.refresh(db_instance)
        else:
            with Session(self.engine) as session:
                session.add(db_instance)
                session.commit()
                session.refresh(db_instance)
        return self._to_response(db_instance)

    async def get_by_id(self, item_id: str) -> ResponseModel:
        if self.is_async:
            async with AsyncSession(self.engine) as session:
                db_instance = await session.get(self.db_model, item_id)
        else:
            with Session(self.engine) as session:
                db_instance = session.get(self.db_model, item_id)
        if not db_instance:
            raise NotFoundError(f"{self.entity_name} not found")
        return self._to_response(db_instance)

    async def get_all(self, page: int = 1, page_size: int = 10) -> list[ResponseModel]:
        offset = (page - 1) * page_size
        statement = select(self.db_model).offset(offset).limit(page_size)
        if self.is_async:
            async with AsyncSession(self.engine) as session:
                result = await session.execute(statement)
                results = result.scalars().all()
        else:
            with Session(self.engine) as session:
                results = session.exec(statement).all()
        return [self._to_response(instance) for instance in results]

    async def update(self, item_id: str, data: UpdateModel) -> ResponseModel:
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if key in self.column_preprocessors:
                update_data[key] = self.column_preprocessors[key](value)
        if self.is_async:
            async with AsyncSession(self.engine) as session:
                db_instance = await session.get(self.db_model, item_id)
                if not db_instance:
                    raise NotFoundError(f"{self.entity_name} not found")
                for key, value in update_data.items():
                    setattr(db_instance, key, value)
                session.add(db_instance)
                await session.commit()
                await session.refresh(db_instance)
        else:
            with Session(self.engine) as session:
                db_instance = session.get(self.db_model, item_id)
                if not db_instance:
                    raise NotFoundError(f"{self.entity_name} not found")
                for key, value in update_data.items():
                    setattr(db_instance, key, value)
                session.add(db_instance)
                session.commit()
                session.refresh(db_instance)
        return self._to_response(db_instance)

    async def delete(self, item_id: str) -> ResponseModel:
        if self.is_async:
            async with AsyncSession(self.engine) as session:
                db_instance = await session.get(self.db_model, item_id)
                if not db_instance:
                    raise NotFoundError(f"{self.entity_name} not found")
                await session.delete(db_instance)
                await session.commit()
        else:
            with Session(self.engine) as session:
                db_instance = session.get(self.db_model, item_id)
                if not db_instance:
                    raise NotFoundError(f"{self.entity_name} not found")
                session.delete(db_instance)
                session.commit()
        return self._to_response(db_instance)

    async def create_bulk(self, data_list: list[CreateModel]) -> list[ResponseModel]:
        db_instances = []
        for data in data_list:
            data_dict = data.model_dump(exclude_unset=True)
            for key, preprocessor in self.column_preprocessors.items():
                if key in data_dict:
                    data_dict[key] = preprocessor(data_dict[key])
            db_instances.append(self.db_model(**data_dict))
        if self.is_async:
            async with AsyncSession(self.engine) as session:
                session.add_all(db_instances)
                await session.commit()
                for instance in db_instances:
                    await session.refresh(instance)
        else:
            with Session(self.engine) as session:
                session.add_all(db_instances)
                session.commit()
                for instance in db_instances:
                    session.refresh(instance)
        return [self._to_response(instance) for instance in db_instances]
