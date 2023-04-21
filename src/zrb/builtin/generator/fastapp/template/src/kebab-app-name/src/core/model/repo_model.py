from typing import List, Optional, TypeVar, Type
from pydantic import BaseModel
from core.repo.repo import Repo
from core.repo.search_filter import SearchFilter
from core.model.model import Model

Schema = TypeVar('Schema', bound=BaseModel)
SchemaData = TypeVar('SchemaData', bound=BaseModel)
SchemaResult = TypeVar('SchemaResult', bound=BaseModel)


class RepoModel(Model[Schema, SchemaData, SchemaResult]):
    schema_result_cls: Type[SchemaResult]

    def __init__(self, repo: Repo[Schema, SchemaData]):
        self.repo = repo

    def get_by_id(self, id: str) -> Schema:
        return self.repo.get_by_id(id)

    def get_all(self) -> List[Schema]:
        count = self.repo.count()
        limit = 1000
        schema_list: List[Schema] = []
        for offset in range(0, count, limit):
            partial_schema_list = self.repo.get(limit=limit, offset=offset)
            schema_list += partial_schema_list
        return schema_list

    def get(
        self, search_filter: Optional[SearchFilter] = None,
        limit: int = 100, offset: int = 0
    ) -> SchemaResult:
        count = self.repo.count(search_filter)
        data = self.repo.get(search_filter, limit, offset)
        return self.schema_result_cls(count=count, data=data)

    def count(self, search_filter: Optional[SearchFilter] = None) -> int:
        return self.repo.count(search_filter)

    def insert(self, data: SchemaData) -> Schema:
        return self.repo.insert(data)

    def update(self, id: str, data: SchemaData) -> Schema:
        return self.repo.update(id, data)

    def delete(self, id: str) -> Schema:
        return self.repo.delete(id)
