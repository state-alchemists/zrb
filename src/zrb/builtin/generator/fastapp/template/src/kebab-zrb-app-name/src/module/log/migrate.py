from config import app_enable_log_module
from helper.migration import migrate
from integration.db_connection import engine
from integration.log import logger
from module.log.integration import Base


async def migrate_log():
    if not app_enable_log_module:
        logger.info('🥪 Skip DB migration for "log"')
        return
    logger.info('🥪 Perform DB migration for "log"')
    await migrate(engine=engine, Base=Base)
