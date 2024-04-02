from integration.messagebus import publisher
from module.snake_zrb_module_name.entity.snake_zrb_entity_name.model import (
    PascalZrbEntityNameModel,
)
from module.snake_zrb_module_name.integration.repo.snake_zrb_entity_name_repo import (
    snake_zrb_entity_name_repo,
)

snake_zrb_entity_name_model: PascalZrbEntityNameModel = PascalZrbEntityNameModel(
    snake_zrb_entity_name_repo, publisher
)
