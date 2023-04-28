from core.model import Model, RepoModel
from module.snake_module_name.schema.snake_entity_name import (
    PascalEntityName, PascalEntityNameData, PascalEntityNameResult
)


class PascalEntityNameModel(
    Model[PascalEntityName, PascalEntityNameData, PascalEntityNameResult]
):
    pass


class PascalEntityNameRepoModel(
    RepoModel[PascalEntityName, PascalEntityNameData, PascalEntityNameResult],
    PascalEntityNameModel
):
    schema_result_cls = PascalEntityNameResult
