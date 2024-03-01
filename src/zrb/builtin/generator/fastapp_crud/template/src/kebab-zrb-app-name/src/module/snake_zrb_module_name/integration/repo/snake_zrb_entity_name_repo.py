from integration.db_connection import engine
from integration.log import logger
from module.snake_zrb_module_name.entity.snake_zrb_entity_name.repo import (
    PascalZrbEntityNameDBRepo,
    PascalZrbEntityNameRepo,
)

snake_zrb_entity_name_repo: PascalZrbEntityNameRepo = PascalZrbEntityNameDBRepo(
    logger=logger, engine=engine
)
