from config import (
    app_enable_auth_module
)
from component.log import logger
from component.db_connection import engine
from helper.migration import migrate
from module.auth.component import Base
from module.auth.register_permission import register_permission


async def migrate_auth():
    if not app_enable_auth_module:
        logger.info('🥪 Skip DB migration for "auth"')
        return
    logger.info('🥪 Perform DB migration for "auth"')
    await migrate(engine=engine, Base=Base)
    logger.info('🥪 Register permissions')
    await register_permission()
