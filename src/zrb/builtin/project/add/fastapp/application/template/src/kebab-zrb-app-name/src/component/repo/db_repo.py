import logging
from typing import Any, List, Mapping, Optional, Type, TypeVar

from component.repo.repo import Repo
from component.repo.search_filter import SearchFilter
from helper.value import utcnow
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import InstrumentedAttribute
from sqlalchemy.sql._typing import _ColumnExpressionArgument
from ulid import ULID

Schema = TypeVar("Schema", bound=BaseModel)
SchemaData = TypeVar("SchemaData", bound=BaseModel)
DBEntity = TypeVar("DBEntity", bound=Any)


class DBRepo(Repo[Schema, SchemaData]):
    schema_cls: Type[Schema]
    db_entity_cls: Type[DBEntity]

    def __init__(
        self,
        logger: logging.Logger,
        engine: Engine,
    ):
        self.logger = logger
        self.engine = engine
        self.db_entity_attribute_names: List[str] = dir(self.db_entity_cls)
        self._keyword_fields: Optional[List[InstrumentedAttribute]] = None

    async def get_by_id(self, id: str) -> Schema:
        """
        Find a record by id.
        """
        db = self._get_db_session()
        try:
            search_filter = self.db_entity_cls.id == id
            db_entity = self._get_one_by_criterion(db, search_filter)
            return self._db_entity_to_schema(db, db_entity)
        finally:
            db.close()

    async def get(
        self,
        search_filter: Optional[SearchFilter] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Schema]:
        """
        Find multiple records by keyword with limit and offset.
        """
        db = self._get_db_session()
        try:
            search_filter = self._ensure_search_filter(search_filter)
            criterion = self._search_filter_to_criterion(search_filter)
            db_entities = self._get_by_criterion(db, criterion, limit, offset)
            return [
                self._db_entity_to_schema(db, db_entity) for db_entity in db_entities
            ]
        finally:
            db.close()

    async def count(self, search_filter: Optional[SearchFilter] = None) -> int:
        """
        Count records by keyword.
        """
        db = self._get_db_session()
        try:
            search_filter = self._ensure_search_filter(search_filter)
            criterion = self._search_filter_to_criterion(search_filter)
            return self._count_by_criterion(db, criterion)
        finally:
            db.close()

    async def insert(self, data: SchemaData) -> Schema:
        """
        Insert a new record.
        """
        db = self._get_db_session()
        try:
            db_entity = self.db_entity_cls(
                **self._schema_data_to_db_entity_map(db, data),
            )
            if "id" in self.db_entity_attribute_names:
                new_id = self.generate_id()
                db_entity.id = new_id
            if "created_at" in self.db_entity_attribute_names:
                db_entity.created_at = utcnow()
            if "updated_at" in self.db_entity_attribute_names:
                db_entity.updated_at = utcnow()
            db.add(db_entity)
            db.commit()
            db.refresh(db_entity)
            return self._db_entity_to_schema(db, db_entity)
        except Exception:
            self.logger.error(
                f"Error while inserting into {self.db_entity_cls} "
                + f"with schema_data: {data}"
            )
            raise
        finally:
            db.close()

    def generate_id(self) -> str:
        return str(ULID())

    async def update(self, id: str, data: SchemaData) -> Schema:
        """
        Update a record.
        """
        db = self._get_db_session()
        try:
            db_entity = self._get_one_by_criterion(db, self.db_entity_cls.id == id)
            db_entity_map = self._schema_data_to_db_entity_map(db, data)
            for field, value in db_entity_map.items():
                if field == "created_at" or field == "created_by":
                    continue
                setattr(db_entity, field, value)
            if "updated_at" in self.db_entity_attribute_names:
                db_entity.updated_at = utcnow()
            db.add(db_entity)
            db.commit()
            db.refresh(db_entity)
            return self._db_entity_to_schema(db, db_entity)
        except Exception:
            self.logger.error(
                f"Error while updating {self.db_entity_cls} "
                + f"with id: {id}, schema_data: {data}"
            )
            raise
        finally:
            db.close()

    async def delete(self, id: str) -> Schema:
        """
        Delete a record.
        """
        db = self._get_db_session()
        try:
            db_entity = self._get_one_by_criterion(db, self.db_entity_cls.id == id)
            db.delete(db_entity)
            db.commit()
            return self._db_entity_to_schema(db, db_entity)
        except Exception:
            self.logger.error(
                f"Error while deleting {self.db_entity_cls} with id: {id}"
            )
            raise
        finally:
            db.close()

    def _get_db_session(self) -> Session:
        """
        Return a db session.
        """
        return Session(self.engine, expire_on_commit=False)

    def _get_by_criterion(
        self,
        db: Session,
        criterion: _ColumnExpressionArgument[bool],
        limit: int = 100,
        offset: int = 0,
    ) -> List[DBEntity]:
        try:
            db_query = db.query(self.db_entity_cls).filter(criterion)
            if "created_at" in self.db_entity_attribute_names:
                db_query = db_query.order_by(self.db_entity_cls.created_at.desc())
            return db_query.offset(offset).limit(limit).all()
        except Exception:
            self.logger.error(
                f"Error while getting {self.db_entity_cls} "
                + f"with criterion: {criterion}, "
                + f"limit: {limit}, offset: {offset}"
            )
            raise

    def _count_by_criterion(
        self, db: Session, criterion: _ColumnExpressionArgument[bool]
    ) -> int:
        try:
            return db.query(self.db_entity_cls).filter(criterion).count()
        except Exception:
            self.logger.error(
                f"Error while counting for {self.db_entity_cls} "
                + f"with criterion: {criterion}"
            )
            raise

    def _get_one_by_criterion(
        self, db: Session, criterion: _ColumnExpressionArgument[bool]
    ) -> DBEntity:
        try:
            db_entity = db.query(self.db_entity_cls).filter(criterion).first()
            if db_entity is None:
                raise ValueError(
                    f"Not found: Cannot find a {self.db_entity_cls} "
                    + f"with criterion: {criterion}"
                )
            return db_entity
        except Exception:
            self.logger.error(
                f"Error while getting a {self.db_entity_cls} "
                + f"with criterion: {criterion}"
            )
            raise

    def _schema_data_to_db_entity_map(
        self, db: Session, schema_data: SchemaData
    ) -> Mapping[str, Any]:
        """
        Convert entity_data into dictionary
        The result of this convertion is used for inserting/updating db_entity.
        """
        entity_dict = schema_data.model_dump()
        return {
            field: value
            for field, value in entity_dict.items()
            if field in self.db_entity_attribute_names
        }

    def _db_entity_to_schema(self, db: Session, db_entity: DBEntity) -> Schema:
        """
        Convert db_entity into schema.
        """
        return self.schema_cls.from_orm(db_entity)

    def _search_filter_to_criterion(
        self, search_filter: SearchFilter
    ) -> _ColumnExpressionArgument[bool]:
        """
        Return keyword filtering.
        The result is usually used to invoke find/count.
        """
        keyword = search_filter.keyword
        if keyword == "":
            return True
        like_keyword = "%{}%".format(keyword)
        keyword_criterion = [
            keyword_field.like(like_keyword)
            for keyword_field in self._get_keyword_fields()
        ]
        return or_(*keyword_criterion)

    def _get_keyword_fields(self) -> List[InstrumentedAttribute]:
        """
        Return list of fields for keyword filtering
        """
        if self._keyword_fields is not None:
            return self._keyword_fields
        self._keyword_fields = []
        for field_name in self.db_entity_attribute_names:
            field = getattr(self.db_entity_cls, field_name, None)
            if type(field) != InstrumentedAttribute:
                continue
            field_type = getattr(field, "type", None)
            if field_type is None:
                continue
            str_field_type = str(field_type)
            if not (
                str_field_type.upper().startswith("VARCHAR")
                or str_field_type.upper().startswith("TEXT")
            ):
                continue
            self._keyword_fields.append(field)
        return self._keyword_fields

    def _ensure_search_filter(self, search_filter: Optional[SearchFilter]):
        if search_filter is None:
            return SearchFilter(keyword="", criterion={})
        return search_filter
