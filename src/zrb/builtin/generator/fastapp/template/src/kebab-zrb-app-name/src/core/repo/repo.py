from typing import Generic, List, Optional, TypeVar
from pydantic import BaseModel
from abc import ABC, abstractmethod
from core.repo.search_filter import SearchFilter

SchemaData = TypeVar('SchemaData', bound=BaseModel)
Schema = TypeVar('Schema', bound=BaseModel)


class Repo(Generic[Schema, SchemaData], ABC):

    @abstractmethod
    async def get_by_id(self, id: str) -> Schema:
        pass

    @abstractmethod
    async def get(
        self, search_filter: Optional[SearchFilter], limit: int, offset: int
    ) -> List[Schema]:
        pass

    @abstractmethod
    async def count(self, search_filter: Optional[SearchFilter]) -> int:
        pass

    @abstractmethod
    async def insert(self, data: SchemaData) -> Schema:
        pass

    @abstractmethod
    async def update(self, id: str, data: SchemaData) -> Schema:
        pass

    @abstractmethod
    async def delete(self, id: str) -> Schema:
        pass
