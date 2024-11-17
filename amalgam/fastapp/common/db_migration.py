from alembic import context
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase


def run_db_migration(
    db_url: str, migration_table_name: str, baseclass: DeclarativeBase
):
    target_metadata = baseclass.metadata
    # Set up the Alembic configuration
    alembic_config = Config()
    alembic_config.set_main_option("sqlalchemy.url", db_url)
    alembic_config.set_main_option("script_location", "migrations")  # Update this if needed
    alembic_config.set_main_option("version_table", migration_table_name)
    # Create the database engine
    engine = create_engine(db_url)

    def run_migration_online():
        # Configure and run migrations
        with engine.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                version_table=migration_table_name,  # Custom migration table
            )
            with context.begin_transaction():
                context.run_migrations()

    # Run migrations
    with context.EnvironmentContext(alembic_config, target_metadata):
        run_migration_online()
