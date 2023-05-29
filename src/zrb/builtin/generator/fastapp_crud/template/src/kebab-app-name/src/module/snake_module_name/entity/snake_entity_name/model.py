from module.log.core.historical_repo_model import HistoricalRepoModel
from module.snake_module_name.schema.snake_entity_name import (
    PascalEntityName, PascalEntityNameData, PascalEntityNameResult
)


class PascalEntityNameModel(
    HistoricalRepoModel[PascalEntityName, PascalEntityNameData, PascalEntityNameResult]
):
    schema_result_cls = PascalEntityNameResult
    log_entity_name = 'snake_entity_name'
