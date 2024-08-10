from config import APP_ENABLE_AUTH_MODULE
from helper.migration import migrate
from integration.db_connection import engine
from integration.log import logger
from module.auth.integration import Base
from module.auth.register_permission import register_permission


async def migrate_auth():
    if not APP_ENABLE_AUTH_MODULE:
        logger.info('🥪 Skip DB migration for "auth"')
        return
    logger.info('🥪 Perform DB migration for "auth"')
    await migrate(engine=engine, Base=Base)
    logger.info("🥪 Register permissions")
    await register_permission()
