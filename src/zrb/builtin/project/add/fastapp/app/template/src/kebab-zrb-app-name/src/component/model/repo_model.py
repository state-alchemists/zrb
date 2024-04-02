from typing import Generic, List, Optional, Type, TypeVar

from component.repo.repo import Repo
from component.repo.search_filter import SearchFilter
from pydantic import BaseModel

Schema = TypeVar("Schema", bound=BaseModel)
SchemaData = TypeVar("SchemaData", bound=BaseModel)
SchemaResult = TypeVar("SchemaResult", bound=BaseModel)


class RepoModel(Generic[Schema, SchemaData, SchemaResult]):
    schema_result_cls: Type[SchemaResult]

    def __init__(self, repo: Repo[Schema, SchemaData]):
        self.repo = repo

    async def get_by_id(self, id: str) -> Schema:
        return await self.repo.get_by_id(id)

    async def get_all(self) -> List[Schema]:
        count = await self.repo.count()
        limit = 1000
        schema_list: List[Schema] = []
        for offset in range(0, count, limit):
            partial_schema_list = await self.repo.get(limit=limit, offset=offset)
            schema_list += partial_schema_list
        return schema_list

    async def get(
        self,
        search_filter: Optional[SearchFilter] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> SchemaResult:
        count = await self.repo.count(search_filter)
        data = await self.repo.get(search_filter, limit, offset)
        return self.schema_result_cls(count=count, data=data)

    async def count(self, search_filter: Optional[SearchFilter] = None) -> int:
        return await self.repo.count(search_filter)

    async def insert(self, data: SchemaData) -> Schema:
        return await self.repo.insert(data)

    async def update(self, id: str, data: SchemaData) -> Schema:
        return await self.repo.update(id, data)

    async def delete(self, id: str) -> Schema:
        return await self.repo.delete(id)
