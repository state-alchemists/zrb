from core.model import RepoModel
from module.snake_module_name.schema.snake_entity_name import (
    PascalEntityName, PascalEntityNameData, PascalEntityNameResult
)


class PascalEntityNameModel(
    RepoModel[PascalEntityName, PascalEntityNameData, PascalEntityNameResult]
):
    schema_result_cls = PascalEntityNameResult
