from ...common.db_migration import run_db_migration
from ...config import (
    APP_DB_MIGRATION_TABLE,
    APP_DB_MIGRATION_URL,
    APP_MODE,
    APP_MODULES,
    APP_REPOSITORY_TYPE,
)
from .db.baseclass import Base

if APP_REPOSITORY_TYPE == "db" and (
    (APP_MODE == "microservices" and "auth" in APP_MODULES) or APP_MODE == "monolith"
):
    run_db_migration(
        db_url=APP_DB_MIGRATION_URL,
        migration_table_name=APP_DB_MIGRATION_TABLE,
        baseclass=Base,
    )
