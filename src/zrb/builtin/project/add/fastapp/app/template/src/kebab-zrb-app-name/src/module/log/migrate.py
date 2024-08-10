from config import APP_ENABLE_LOG_MODULE
from helper.migration import migrate
from integration.db_connection import engine
from integration.log import logger
from module.log.integration import Base


async def migrate_log():
    if not APP_ENABLE_LOG_MODULE:
        logger.info('🥪 Skip DB migration for "log"')
        return
    logger.info('🥪 Perform DB migration for "log"')
    await migrate(engine=engine, Base=Base)
