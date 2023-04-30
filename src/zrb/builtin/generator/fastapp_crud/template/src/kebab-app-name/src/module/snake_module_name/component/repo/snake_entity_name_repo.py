from component.log import logger
from component.db_connection import engine
from module.snake_module_name.entity.snake_entity_name.repo import (
    PascalEntityNameRepo, PascalEntityNameDBRepo
)

snake_entity_name_repo: PascalEntityNameRepo = PascalEntityNameDBRepo(
    logger=logger, engine=engine
)
