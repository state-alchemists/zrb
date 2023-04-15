from typing import Any, Generic, List, Mapping, Optional, TypeVar, Type
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import InstrumentedAttribute

import uuid
import datetime
import logging

SchemaData = TypeVar('SchemaData', bound=BaseModel)
Schema = TypeVar('Schema', bound=BaseModel)
DBEntity = TypeVar('DBEntity', bound=Any)


class DBRepo(Generic[DBEntity, Schema, SchemaData]):
    schema_class: Type[Schema]
    db_entity_class: Type[DBEntity]

    def __init__(
        self,
        logger: logging.Logger,
        engine: Engine,
    ):
        self.logger = logger
        self.engine = engine
        self.db_entity_attribute_names: List[str] = dir(self.db_entity_class)
        self.schema_attribute_names: List[str] = dir(self.schema_class)

    def get_one(self, id: str) -> Optional[Schema]:
        '''
        Find a record by id.
        '''
        db = self._create_db_session()
        try:
            search_filter = self.db_entity_class.id == id
            return self._get_one_by_filter(db, search_filter)
        finally:
            db.close()

    def get(
        self, keyword: str, limit: int = 100, offset: int = 0
    ) -> List[Schema]:
        '''
        Find multiple records by keyword with limit and offset.
        '''
        db = self._create_db_session()
        try:
            search_filter = self._get_search_filter(db, keyword)
            return self._get_by_filter(db, search_filter, limit, offset)
        finally:
            db.close()

    def count(self, keyword: str) -> int:
        '''
        Count records by keyword.
        '''
        db = self._create_db_session()
        try:
            search_filter = self._get_search_filter(db, keyword)
            return self._count_by_filter(db, search_filter)
        finally:
            db.close()

    def insert(self, schema_data: SchemaData) -> Optional[Schema]:
        '''
        Insert a new record.
        '''
        db = self._create_db_session()
        try:
            db_entity = self.db_entity_class(
                ** self._schema_data_to_db_entity_dict(schema_data),
            )
            if 'id' in self.db_entity_attribute_names:
                new_id = str(uuid.uuid4())
                db_entity.id = new_id
            if 'created_at' in self.db_entity_attribute_names:
                db_entity.created_at = datetime.datetime.utcnow()
            if 'updated_at' in self.db_entity_attribute_names:
                db_entity.updated_at = datetime.datetime.utcnow()
            db.add(db_entity)
            db.commit()
            db.refresh(db_entity)
            return self._db_entity_to_schema(db_entity)
        except Exception:
            self.logger.error(
                f'Error while inserting into {self.db_entity_class} ' +
                f'with schema_data: {schema_data}'
            )
            raise
        finally:
            db.close()

    def update(
        self, id: str, schema_data: SchemaData
    ) -> Optional[Schema]:
        '''
        Update a record.
        '''
        db = self._create_db_session()
        try:
            db_entity = db.query(self.db_entity_class).filter(
                self.db_entity_class.id == id
            ).first()
            if db_entity is None:
                return None
            db_entity_dict = self._schema_data_to_db_entity_dict(
                schema_data
            )
            for field, value in db_entity_dict.items():
                if field == 'created_at' or field == 'created_by':
                    continue
                setattr(db_entity, field, value)
            if 'updated_at' in self.db_entity_attribute_names:
                db_entity.updated_at = datetime.datetime.utcnow()
            db.add(db_entity)
            db.commit()
            db.refresh(db_entity)
            return self._db_entity_to_schema(db_entity)
        except Exception:
            self.logger.error(
                f'Error while updating {self.db_entity_class} ' +
                f'with id: {id}, schema_data: {schema_data}'
            )
            raise
        finally:
            db.close()

    def delete(self, id: str) -> Optional[Schema]:
        '''
        Delete a record.
        '''
        db = self._create_db_session()
        try:
            db_entity = db.query(self.db_entity_class).filter(
                self.db_entity_class.id == id
            ).first()
            if db_entity is None:
                return None
            db.delete(db_entity)
            db.commit()
            return self._db_entity_to_schema(db_entity)
        except Exception:
            self.logger.error(
                f'Error while deleting {self.db_entity_class} with id: {id}'
            )
            raise
        finally:
            db.close()

    def _get_by_filter(
        self,
        db: Session,
        search_filter: Any,
        limit: int = 100,
        offset: int = 0
    ) -> List[Schema]:
        try:
            db_query = db.query(self.db_entity_class).filter(
                search_filter
            )
            if 'created_at' in self.db_entity_attribute_names:
                db_query = db_query.order_by(
                    self.db_entity_class.created_at.desc()
                )
            db_entities = db_query.offset(offset).limit(limit).all()
            return [
                self._db_entity_to_schema(db_entity)
                for db_entity in db_entities
            ]
        except Exception:
            self.logger.error(
                f'Error while looking for {self.db_entity_class} ' +
                f'with search filter: {search_filter}, ' +
                f'limit: {limit}, offset: {offset}'
            )
            raise

    def _count_by_filter(
        self,
        db: Session,
        search_filter: Any,
    ) -> List[Schema]:
        try:
            return db.query(self.db_entity_class).filter(
                search_filter
            ).count()
        except Exception:
            self.logger.error(
                f'Error while conunting for {self.db_entity_class} ' +
                f'with search filter: {search_filter}'
            )
            raise

    def _get_one_by_filter(
        self, db: Session, search_filter: Any
    ) -> Optional[Schema]:
        try:
            db_entity = db.query(self.db_entity_class).filter(
                search_filter
            ).first()
            if db_entity is None:
                return None
            return self._db_entity_to_schema(db_entity)
        except Exception:
            self.logger.error(
                f'Error while looking for {self.db_entity_class} ' +
                f'with search filter: {search_filter}'
            )
            raise

    def _get_keyword_fields(self) -> List[InstrumentedAttribute]:
        '''
        Return list of fields for keyword filtering
        '''
        return [
            getattr(self.db_entity_class, field)
            for field in self.db_entity_attribute_names
            if type(
                getattr(self.db_entity_class, field)
            ) == InstrumentedAttribute
        ]

    def _schema_data_to_db_entity_dict(
        self, schema_data: SchemaData
    ) -> Mapping[str, Any]:
        '''
        Convert entity_data into dictionary
        The result of this convertion is used for inserting/updating db_entity.
        '''
        entity_dict = schema_data.dict()
        return {
            field: value
            for field, value in entity_dict.items()
            if field in self.db_entity_attribute_names
        }

    def _db_entity_to_schema(self, db_entity: DBEntity) -> Schema:
        '''
        Convert db_entity into schema.
        '''
        return self.schema_class.from_orm(db_entity)

    def _get_search_filter(self, db: Session, keyword: str) -> Any:
        '''
        Return keyword filtering.
        The result is usually used to invoke find/count.
        '''
        like_keyword = '%{}%'.format(keyword) if keyword != '' else '%'
        keyword_filter = [
            keyword_field.like(like_keyword)
            for keyword_field in self._get_keyword_fields()
        ]
        return or_(*keyword_filter)

    def _create_db_session(self) -> Session:
        '''
        Return a db session.
        '''
        return Session(self.engine, expire_on_commit=False)
