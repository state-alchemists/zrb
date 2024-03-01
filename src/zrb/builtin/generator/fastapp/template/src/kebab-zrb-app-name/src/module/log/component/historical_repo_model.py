from typing import Type, TypeVar

import jsons
from component.messagebus.messagebus import Publisher
from component.model.repo_model import RepoModel
from component.repo.repo import Repo
from module.log.schema.activity import ActivityData
from pydantic import BaseModel

Schema = TypeVar("Schema", bound=BaseModel)
SchemaData = TypeVar("SchemaData", bound=BaseModel)
SchemaResult = TypeVar("SchemaResult", bound=BaseModel)


class HistoricalRepoModel(RepoModel[Schema, SchemaData, SchemaResult]):
    schema_result_cls: Type[SchemaResult]
    log_entity_name: str

    def __init__(self, repo: Repo[Schema, SchemaData], publisher: Publisher):
        super().__init__(repo)
        self.publisher = publisher

    async def insert(self, data: SchemaData) -> Schema:
        result = await super().insert(data)
        await self._publish_activity(action="insert", result=result)
        return result

    async def update(self, id: str, data: SchemaData) -> Schema:
        result = await self.repo.update(id, data)
        await self._publish_activity(action="update", result=result)
        return result

    async def delete(self, id: str) -> Schema:
        result = await self.repo.delete(id)
        await self._publish_activity(action="delete", result=result)
        return result

    async def _publish_activity(self, action: str, result: Schema):
        activity_data = ActivityData(
            action=action,
            entity=self.log_entity_name,
            data=jsons.dumps(result.model_dump()),
        )
        await self.publisher.publish("log_new_activity", activity_data.model_dump())
