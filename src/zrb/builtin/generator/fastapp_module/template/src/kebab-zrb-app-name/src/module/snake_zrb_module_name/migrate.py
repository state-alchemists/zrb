from config import (
    app_enable_snake_zrb_module_name_module
)
from component.log import logger
from component.db_connection import engine
from helper.migration import migrate
from module.snake_zrb_module_name.component import Base


async def migrate_snake_zrb_module_name():
    if not app_enable_snake_zrb_module_name_module:
        logger.info('🥪 Skip DB migration for "snake_zrb_module_name"')
        return
    logger.info('🥪 Perform DB migration for "snake_zrb_module_name"')
    await migrate(engine=engine, Base=Base)
