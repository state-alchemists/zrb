import datetime
from typing import Any, Callable, Generic, Type, TypeVar

from my_app_name.common.error import InvalidValueError, NotFoundError
from sqlalchemy import Engine, func, select
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

    def __init__(self, engine: Engine | AsyncEngine):
        self.engine = engine
        self.is_async = isinstance(engine, AsyncEngine)

    def _select(self) -> Select:
        """
        Default select statement, ensures the query is consistent
        for single and bulk operations.
        """
        return select(self.db_model)

    def _rows_to_responses(self, rows: list[tuple[Any]]) -> list[ResponseModel]:
        """
        Transforms query result rows into a list of ResponseModel.
        Rows is typically a list of tuple since both of these return list of tuples:
        - session.exec(select(Model)).all() --> [(Model,), ...]
        - session.exec(select(Model, Other).join(Other)).all() --> [(Model, Other), ...]
        """
        return [self.response_model(**row[0].model_dump()) for row in rows]

    def _ensure_one(self, responses: list[ResponseModel]) -> ResponseModel:
        """
        Make sure responses contain a single element.
        If that was the case, return that element.
        """
        if not responses:
            raise NotFoundError(f"{self.entity_name} not found")
        if len(responses) > 1:
            raise InvalidValueError(f"Duplicate {self.entity_name}")
        return responses[0]

    async def _execute_select_statement(self, statement: Select) -> list[tuple[Any]]:
        """
        Execute select statement and return the result.
        """
        if self.is_async:
            async with AsyncSession(self.engine) as session:
                result = await session.execute(statement)
                return result.all()
        with Session(self.engine) as session:
            result = session.exec(statement)
            return result.all()

    async def create(self, data: CreateModel) -> ResponseModel:
        """
        Create a new record and return the created ResponseModel.
        """
        new_data = data.model_dump(exclude_unset=True)
        if hasattr(self.db_model, "created_at"):
            new_data["created_at"] = datetime.datetime.now(datetime.timezone.utc)
        for key, preprocessor in self.column_preprocessors.items():
            if not hasattr(self.db_model, key):
                raise InvalidValueError(f"Invalid {self.entity_name} property: {key}")
            if key in new_data:
                new_data[key] = preprocessor(new_data[key])
        # Construct db instance
        db_instance = self.db_model(**new_data)
        # Execute statement
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
        # Fetch the created record using the default select
        select_statement = self._select().where(self.db_model.id == db_instance.id)
        rows = await self._execute_select_statement(select_statement)
        responses = self._rows_to_responses(rows)
        return self._ensure_one(responses)

    async def get_by_id(self, item_id: str) -> ResponseModel:
        """
        Retrieve an item by its ID and return the ResponseModel.
        """
        select_statement = self._select().where(self.db_model.id == item_id)
        rows = await self._execute_select_statement(select_statement)
        responses = self._rows_to_responses(rows)
        return self._ensure_one(responses)

    async def count(self, filters: list[ClauseElement] | None = None) -> int:
        """
        Count the number of records matching the filters.
        """
        statement = select(func.count()).select_from(self._select().subquery())
        if filters:
            statement = statement.where(*filters)
        # Execute statement
        if self.is_async:
            async with AsyncSession(self.engine) as session:
                result = await session.execute(statement)
        else:
            with Session(self.engine) as session:
                result = session.exec(statement)
        # Return response
        return result.scalar()

    async def get_all(
        self,
        page: int = 1,
        page_size: int = 10,
        filters: list[ClauseElement] | None = None,
        sorts: list[ColumnElement] | None = None,
    ) -> list[ResponseModel]:
        """
        Retrieve paginated results as ResponseModels.
        """
        offset = (page - 1) * page_size
        select_statement = self._select().offset(offset).limit(page_size)
        if filters:
            select_statement = select_statement.where(*filters)
        if sorts:
            select_statement = select_statement.order_by(*sorts)
        # Execute statement
        rows = await self._execute_select_statement(select_statement)
        responses = self._rows_to_responses(rows)
        return responses

    async def update(self, item_id: str, data: UpdateModel) -> ResponseModel:
        """
        Update an existing record by ID and return the updated ResponseModel.
        """
        update_data = data.model_dump(exclude_unset=True)
        if hasattr(self.db_model, "updated_at"):
            update_data["updated_at"] = datetime.datetime.now(datetime.timezone.utc)

        for key, value in update_data.items():
            if not hasattr(self.db_model, key):
                raise InvalidValueError(f"Invalid {self.entity_name} property: {key}")
            if key in self.column_preprocessors:
                update_data[key] = self.column_preprocessors[key](value)
        # Execute statement
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
        # Fetch updated instance
        select_statement = self._select().where(self.db_model.id == item_id)
        rows = await self._execute_select_statement(select_statement)
        responses = self._rows_to_responses(rows)
        return self._ensure_one(responses)

    async def create_bulk(self, data_list: list[CreateModel]) -> list[ResponseModel]:
        db_instances = []
        now = datetime.datetime.now(datetime.timezone.utc)
        for data in data_list:
            new_data = data.model_dump(exclude_unset=True)
            if hasattr(self.db_model, "created_at"):
                new_data["created_at"] = now
            for key, preprocessor in self.column_preprocessors.items():
                if not hasattr(self.db_model, key):
                    raise InvalidValueError(
                        f"Invalid {self.entity_name} property: {key}"
                    )
                if key in new_data:
                    new_data[key] = preprocessor(new_data[key])
            db_instances.append(self.db_model(**new_data))
        if self.is_async:
            async with AsyncSession(self.engine) as session:
                session.add_all(db_instances)
                await session.commit()
                await session.refresh(db_instances)
        else:
            with Session(self.engine) as session:
                session.add_all(db_instances)
                session.commit()
                session.refresh(db_instances)
        select_statement = self._select().where(
            self.db_model.id.in_([instance.id for instance in db_instances])
        )
        rows = await self._execute_select_statement(select_statement)
        responses = self._rows_to_responses(rows)
        return responses

    async def delete(self, item_id: str) -> ResponseModel:
        select_statement = self._select().where(self.db_model.id == item_id)
        rows = await self._execute_select_statement(select_statement)
        responses = self._rows_to_responses(rows)
        response = self._ensure_one(responses)
        if self.is_async:
            async with AsyncSession(self.engine) as session:
                statement = self._select().where(self.db_model.id == item_id)
                result = await session.execute(statement)
                db_instance = result.scalar_one_or_none()
                if not db_instance:
                    raise NotFoundError(f"{self.entity_name} not found")
                await session.delete(db_instance)
                await session.commit()
        else:
            with Session(self.engine) as session:
                statement = self._select().where(self.db_model.id == item_id)
                result = session.exec(statement)
                db_instance = result.scalar_one_or_none()
                if not db_instance:
                    raise NotFoundError(f"{self.entity_name} not found")
                session.delete(db_instance)
                session.commit()
        return response
