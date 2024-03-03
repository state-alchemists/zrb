from config import app_enable_snake_zrb_module_name_module
from helper.migration import migrate
from integration.db_connection import engine
from integration.log import logger
from module.snake_zrb_module_name.integration import Base


async def migrate_snake_zrb_module_name():
    if not app_enable_snake_zrb_module_name_module:
        logger.info('🥪 Skip DB migration for "snake_zrb_module_name"')
        return
    logger.info('🥪 Perform DB migration for "snake_zrb_module_name"')
    await migrate(engine=engine, Base=Base)
