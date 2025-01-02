import datetime
from contextlib import asynccontextmanager
from typing import Any, Callable, Generic, Type, TypeVar

import ulid
from my_app_name.common.error import InvalidValueError, NotFoundError
from my_app_name.common.parser_factory import parse_filter_param, parse_sort_param
from sqlalchemy import Engine, delete, func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.sql import Select
from sqlmodel import Session, SQLModel

DBModel = TypeVar("DBModel", bound=SQLModel)
ResponseModel = TypeVar("ResponseModel", bound=SQLModel)
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

    def _select(self) -> Select:
        return select(self.db_model)

    def _rows_to_responses(self, rows: list[tuple[Any]]) -> list[ResponseModel]:
        return [self.response_model.model_validate(row[0]) for row in rows]

    def _ensure_one(self, responses: list[ResponseModel]) -> ResponseModel:
        if not responses:
            raise NotFoundError(f"{self.entity_name} not found")
        if len(responses) > 1:
            raise InvalidValueError(f"Duplicate {self.entity_name}")
        return responses[0]

    @asynccontextmanager
    async def _session_scope(self):
        if self.is_async:
            async with AsyncSession(self.engine) as session:
                async with session.begin():
                    yield session
        else:
            with Session(self.engine) as session:
                with session.begin():
                    yield session

    async def _commit(self, session: Session | AsyncSession):
        if self.is_async:
            await session.commit()
        else:
            session.commit()

    async def _execute_statement(self, session, statement: Any) -> Any:
        if self.is_async:
            return await session.execute(statement)
        else:
            return session.execute(statement)

    async def get_by_id(self, id: str) -> ResponseModel:
        statement = self._select().where(self.db_model.id == id)
        async with self._session_scope() as session:
            result = await self._execute_statement(session, statement)
            responses = self._rows_to_responses(result.all())
            return self._ensure_one(responses)

    async def get_by_ids(self, id_list: list[str]) -> list[ResponseModel]:
        statement = self._select().where(self.db_model.id.in_(id_list))
        async with self._session_scope() as session:
            result = await self._execute_statement(session, statement)
            return [
                self.db_model(**entity.model_dump())
                for entity in result.scalars().all()
            ]

    async def count(self, filter: str | None = None) -> int:
        count_statement = select(func.count(1)).select_from(self.db_model)
        if filter:
            filter_param = parse_filter_param(self.db_model, filter)
            count_statement = count_statement.where(*filter_param)
        async with self._session_scope() as session:
            result = await self._execute_statement(session, count_statement)
            return result.scalar_one()

    async def get(
        self,
        page: int = 1,
        page_size: int = 10,
        filter: str | None = None,
        sort: str | None = None,
    ) -> list[ResponseModel]:
        offset = (page - 1) * page_size
        statement = self._select().offset(offset).limit(page_size)
        if filter:
            filter_param = parse_filter_param(self.db_model, filter)
            statement = statement.where(*filter_param)
        if sort:
            sort_param = parse_sort_param(self.db_model, sort)
            statement = statement.order_by(*sort_param)
        async with self._session_scope() as session:
            result = await self._execute_statement(session, statement)
            return [
                self.db_model(**entity.model_dump())
                for entity in result.scalars().all()
            ]

    def _model_to_data_dict(
        self, data: SQLModel, **additional_data: Any
    ) -> dict[str, Any]:
        data_dict = data.model_dump(exclude_unset=True)
        data_dict.update(additional_data)
        for key, preprocessor in self.column_preprocessors.items():
            if key not in data_dict:
                continue
            if not hasattr(self.db_model, key):
                raise InvalidValueError(f"Invalid {self.entity_name} property: {key}")
            data_dict[key] = preprocessor(data_dict[key])
        return data_dict

    async def create(self, data: CreateModel) -> DBModel:
        now = datetime.datetime.now(datetime.timezone.utc)
        data_dict = self._model_to_data_dict(data, created_at=now, id=ulid.new().str)
        async with self._session_scope() as session:
            await self._execute_statement(
                session, insert(self.db_model).values(**data_dict)
            )
            statement = select(self.db_model).where(self.db_model.id == data_dict["id"])
            result = await self._execute_statement(session, statement)
            created_entity = result.scalar_one_or_none()
            if created_entity is None:
                raise NotFoundError(f"{self.entity_name} not found after creation")
            return self.db_model(**created_entity.model_dump())

    async def create_bulk(self, data_list: list[CreateModel]) -> list[DBModel]:
        now = datetime.datetime.now(datetime.timezone.utc)
        data_dicts = [
            self._model_to_data_dict(data, created_at=now, id=ulid.new().str)
            for data in data_list
        ]
        async with self._session_scope() as session:
            await self._execute_statement(
                session, insert(self.db_model).values(data_dicts)
            )
            id_list = [d["id"] for d in data_dicts]
            statement = select(self.db_model).where(self.db_model.id.in_(id_list))
            result = await self._execute_statement(session, statement)
            return [
                self.db_model(**entity.model_dump())
                for entity in result.scalars().all()
            ]

    async def delete(self, id: str) -> DBModel:
        async with self._session_scope() as session:
            statement = select(self.db_model).where(self.db_model.id == id)
            result = await self._execute_statement(session, statement)
            entity = result.scalar_one_or_none()
            if not entity:
                raise NotFoundError(f"{self.entity_name} not found")
            await self._execute_statement(
                session, delete(self.db_model).where(self.db_model.id == id)
            )
            return self.db_model(**entity.model_dump())

    async def delete_bulk(self, id_list: list[str]) -> list[DBModel]:
        async with self._session_scope() as session:
            statement = select(self.db_model).where(self.db_model.id.in_(id_list))
            result = await self._execute_statement(session, statement)
            entities = result.scalars().all()
            await self._execute_statement(
                session, delete(self.db_model).where(self.db_model.id.in_(id_list))
            )
            return [self.db_model(**entity.model_dump()) for entity in entities]

    async def update(self, id: str, data: UpdateModel) -> DBModel:
        now = datetime.datetime.now(datetime.timezone.utc)
        update_data = self._model_to_data_dict(data, updated_at=now)
        async with self._session_scope() as session:
            statement = (
                update(self.db_model)
                .where(self.db_model.id == id)
                .values(**update_data)
            )
            await self._execute_statement(session, statement)
            result = await self._execute_statement(
                session, select(self.db_model).where(self.db_model.id == id)
            )
            updated_instance = result.scalar_one_or_none()
            if not updated_instance:
                raise NotFoundError(f"{self.entity_name} not found")
            return self.db_model(**updated_instance.model_dump())

    async def update_bulk(self, id_list: list[str], data: UpdateModel) -> list[DBModel]:
        now = datetime.datetime.now(datetime.timezone.utc)
        update_data = self._model_to_data_dict(data, updated_at=now)
        update_data = {k: v for k, v in update_data.items() if v is not None}
        if not update_data:
            raise InvalidValueError("No valid update data provided")
        async with self._session_scope() as session:
            statement = (
                update(self.db_model)
                .where(self.db_model.id.in_(id_list))
                .values(**update_data)
            )
            await self._execute_statement(session, statement)
            result = await self._execute_statement(
                session, select(self.db_model).where(self.db_model.id.in_(id_list))
            )
            return [
                self.db_model(**entity.model_dump())
                for entity in result.scalars().all()
            ]
