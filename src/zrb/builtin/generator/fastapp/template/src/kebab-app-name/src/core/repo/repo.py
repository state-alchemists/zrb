from typing import Generic, Optional, TypeVar
from pydantic import BaseModel
from abc import ABC, abstractmethod
from core.repo.search_filter import SearchFilter

SchemaData = TypeVar('SchemaData', bound=BaseModel)
Schema = TypeVar('Schema', bound=BaseModel)


class Repo(Generic[Schema, SchemaData], ABC):

    @abstractmethod
    def get_one(self, id: str) -> Optional[Schema]:
        pass

    @abstractmethod
    def get(
        self, search_filter: Optional[SearchFilter], limit: int, offset: int
    ) -> Optional[Schema]:
        pass

    @abstractmethod
    def count(self, search_filter: Optional[SearchFilter]) -> int:
        pass

    @abstractmethod
    def insert(self, schema_data: SchemaData) -> Optional[Schema]:
        pass

    @abstractmethod
    def update(self, id: str, schema_data: SchemaData) -> Optional[Schema]:
        pass

    @abstractmethod
    def delete(self, id: str) -> Optional[Schema]:
        pass
