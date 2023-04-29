from module.auth.component.repo.snake_entity_name_repo import (
    snake_entity_name_repo
)
from module.auth.entity.snake_entity_name.model import (
    PascalEntityNameModel, PascalEntityNameRepoModel
)

snake_entity_name_model: PascalEntityNameModel = PascalEntityNameRepoModel(
    snake_entity_name_repo
)
