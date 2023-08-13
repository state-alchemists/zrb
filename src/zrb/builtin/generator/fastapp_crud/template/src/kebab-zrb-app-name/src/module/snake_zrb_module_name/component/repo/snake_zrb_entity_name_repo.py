from component.log import logger
from component.db_connection import engine
from module.snake_zrb_module_name.entity.snake_zrb_entity_name.repo import (
    PascalZrbEntityNameRepo, PascalZrbEntityNameDBRepo
)

snake_zrb_entity_name_repo: PascalZrbEntityNameRepo = PascalZrbEntityNameDBRepo(
    logger=logger, engine=engine
)
