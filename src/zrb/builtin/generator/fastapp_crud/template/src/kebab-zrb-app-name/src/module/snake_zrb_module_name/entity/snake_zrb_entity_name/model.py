from module.log.component.historical_repo_model import HistoricalRepoModel
from module.snake_zrb_module_name.schema.snake_zrb_entity_name import (
    PascalZrbEntityName,
    PascalZrbEntityNameData,
    PascalZrbEntityNameResult,
)


class PascalZrbEntityNameModel(
    HistoricalRepoModel[
        PascalZrbEntityName, PascalZrbEntityNameData, PascalZrbEntityNameResult
    ]
):
    schema_result_cls = PascalZrbEntityNameResult
    log_entity_name = "snake_zrb_entity_name"
