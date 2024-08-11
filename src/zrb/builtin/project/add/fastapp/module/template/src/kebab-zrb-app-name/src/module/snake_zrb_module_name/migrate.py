from config import APP_ENABLE_SNAKE_ZRB_MODULE_NAME_MODULE
from helper.migration import migrate
from integration.db_connection import engine
from integration.log import logger
from module.snake_zrb_module_name.integration import Base


async def migrate_snake_zrb_module_name():
    if not APP_ENABLE_SNAKE_ZRB_MODULE_NAME_MODULE:
        logger.info('🥪 Skip DB migration for "snake_zrb_module_name"')
        return
    logger.info('🥪 Perform DB migration for "snake_zrb_module_name"')
    await migrate(engine=engine, Base=Base)
