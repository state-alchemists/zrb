import datetime
from contextlib import asynccontextmanager
from typing import Any, Callable, Generic, Type, TypeVar

import ulid
from my_app_name.common.error import InvalidValueError, NotFoundError
from my_app_name.common.parser_factory import (
    parse_filter_param as default_parse_filter_param,
)
from my_app_name.common.parser_factory import (
    parse_sort_param as default_parse_sort_param,
)
from sqlalchemy import Engine, delete, func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.sql import ClauseElement, ColumnElement, Select
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

    def __init__(
        self,
        engine: Engine | AsyncEngine,
        filter_param_parser: (
            Callable[[SQLModel, str], list[ClauseElement]] | None
        ) = None,
        sort_param_parser: Callable[[SQLModel, str], list[ColumnElement]] | None = None,
    ):
        self.engine = engine
        self._is_async = isinstance(engine, AsyncEngine)
        self._parse_filter_param = (
            filter_param_parser if filter_param_parser else default_parse_filter_param
        )
        self._parse_sort_param = (
            sort_param_parser if sort_param_parser else default_parse_sort_param
        )

    @property
    def is_async(self) -> bool:
        return self._is_async

    def _select(self) -> Select:
        """
        This method is used to contruct select statement for get, get_by_id and get_by_ids.
        To parse the result of the statement, make sure you override _rows_to_response as well.
        """
        return select(self.db_model)

    def _rows_to_responses(self, rows: list[tuple[Any, ...]]) -> list[ResponseModel]:
        """
        This method is used to parse the result of select statement generated by _select.
        """
        return [self.response_model.model_validate(row[0]) for row in rows]

    async def _select_to_response(
        self, query_modifier: Callable[[Select], Any]
    ) -> list[ResponseModel]:
        statement = query_modifier(self._select())
        async with self._session_scope() as session:
            result = await self._execute_statement(session, statement)
            return self._rows_to_responses(result.all())

    def _ensure_one(self, responses: list[ResponseModel]) -> ResponseModel:
        if not responses:
            raise NotFoundError(f"{self.entity_name} not found")
        if len(responses) > 1:
            raise InvalidValueError(f"Duplicate {self.entity_name}")
        return responses[0]

    def _model_to_data_dict(
        self, data: SQLModel, **additional_data: Any
    ) -> dict[str, Any]:
        """
        This method transform SQLModel into dictionary for insert/update operation.
        """
        data_dict = data.model_dump(exclude_unset=True)
        data_dict.update(additional_data)
        for key, preprocessor in self.column_preprocessors.items():
            if key not in data_dict:
                continue
            if not hasattr(self.db_model, key):
                raise InvalidValueError(f"Invalid {self.entity_name} property: {key}")
            data_dict[key] = preprocessor(data_dict[key])
        return data_dict

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
        rows = await self._select_to_response(lambda q: q.where(self.db_model.id == id))
        return self._ensure_one(rows)

    async def get_by_ids(self, id_list: list[str]) -> list[ResponseModel]:
        rows = await self._select_to_response(
            lambda q: q.where(self.db_model.id.in_(id_list))
        )
        # raise error if any id not in id_list
        existing_id_list = [row.id for row in rows]
        inexist_id_list = [id for id in id_list if id not in existing_id_list]
        if len(inexist_id_list) > 0:
            raise NotFoundError(
                f"{self.entity_name} not found, inexist ids: {', '.join(inexist_id_list)}"
            )
        # sort rows
        row_dict = {row.id: row for row in rows}
        return [row_dict[id] for id in id_list]

    async def count(self, filter: str | None = None) -> int:
        count_statement = select(func.count(1)).select_from(self.db_model)
        if filter:
            filter_param = self._parse_filter_param(self.db_model, filter)
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
        return await self._select_to_response(
            self._get_pagination_query_modifier(
                page=page, page_size=page_size, filter=filter, sort=sort
            )
        )

    def _get_pagination_query_modifier(
        self,
        page: int = 1,
        page_size: int = 10,
        filter: str | None = None,
        sort: str | None = None,
    ) -> Callable[[Select], Any]:
        def pagination_query_modifier(statement: Select) -> Any:
            offset = (page - 1) * page_size
            statement = statement.offset(offset).limit(page_size)
            if filter:
                filter_param = self._parse_filter_param(self.db_model, filter)
                statement = statement.where(*filter_param)
            if sort:
                sort_param = self._parse_sort_param(self.db_model, sort)
                statement = statement.order_by(*sort_param)
            return statement

        return pagination_query_modifier

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
        data_dict_list = [
            self._model_to_data_dict(data, created_at=now, id=ulid.new().str)
            for data in data_list
        ]
        id_list = [data_dict["id"] for data_dict in data_dict_list]
        async with self._session_scope() as session:
            await self._execute_statement(
                session, insert(self.db_model).values(data_dict_list)
            )
            statement = select(self.db_model).where(self.db_model.id.in_(id_list))
            result = await self._execute_statement(session, statement)
            row_dict = {
                entity.id: self.db_model(**entity.model_dump())
                for entity in result.scalars().all()
            }
            return [row_dict[id] for id in id_list]

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
            row_dict = {
                entity.id: self.db_model(**entity.model_dump()) for entity in entities
            }
            return [row_dict[id] for id in id_list]

    async def update(self, id: str, data: UpdateModel) -> DBModel:
        now = datetime.datetime.now(datetime.timezone.utc)
        update_data = self._model_to_data_dict(data, updated_at=now)
        update_data = {k: v for k, v in update_data.items() if v is not None}
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
            row_dict = {
                entity.id: self.db_model(**entity.model_dump())
                for entity in result.scalars().all()
            }
            return [row_dict[id] for id in id_list]
