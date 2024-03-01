from config import app_enable_auth_module
from helper.migration import migrate
from integration.db_connection import engine
from integration.log import logger
from module.auth.integration import Base
from module.auth.register_permission import register_permission


async def migrate_auth():
    if not app_enable_auth_module:
        logger.info('🥪 Skip DB migration for "auth"')
        return
    logger.info('🥪 Perform DB migration for "auth"')
    await migrate(engine=engine, Base=Base)
    logger.info("🥪 Register permissions")
    await register_permission()
