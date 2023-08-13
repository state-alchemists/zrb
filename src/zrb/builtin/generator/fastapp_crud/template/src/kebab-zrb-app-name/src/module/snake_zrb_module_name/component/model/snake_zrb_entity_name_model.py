from component.messagebus import publisher
from module.snake_zrb_module_name.component.repo.snake_zrb_entity_name_repo import (
    snake_zrb_entity_name_repo
)
from module.snake_zrb_module_name.entity.snake_zrb_entity_name.model import (
    PascalZrbEntityNameModel
)

snake_zrb_entity_name_model: PascalZrbEntityNameModel = PascalZrbEntityNameModel(
    snake_zrb_entity_name_repo, publisher
)
