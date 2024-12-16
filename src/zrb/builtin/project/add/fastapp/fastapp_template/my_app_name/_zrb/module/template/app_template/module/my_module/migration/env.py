from logging.config import fileConfig

from alembic import context
from my_app_name.config import APP_DB_URL
from my_app_name.module.my_module.migration_metadata import metadata
from sqlalchemy import engine_from_config, pool

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# 🔥 FastApp Modification
MIGRATION_TABLE = "_migration_my_module"
# 🔥 FastApp Modification
config.set_section_option(config.config_ini_section, "sqlalchemy.url", APP_DB_URL)

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


# 🔥 FastApp Modification
def include_object(object, name, type_, reflected, compare_to):
    """
    Filter which objects Alembic should include in migrations.
    Args:
        object: The SQLAlchemy object (table, column, etc.)
        name: The name of the object
        type_: The type of the object ("table", "column", etc.)
        reflected: True if the object is reflected from the database
        compare_to: The object being compared against
    Returns:
        bool: True to include, False to exclude
    """
    # Exclude tables not in metadata
    if type_ == "table" and name not in target_metadata.tables:
        return False  # Skip this table
    return True


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table=MIGRATION_TABLE,  # 🔥 FastApp Modification
        include_object=include_object,  # 🔥 FastApp Modification
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_table=MIGRATION_TABLE,  # 🔥 FastApp Modification
            include_object=include_object,  # 🔥 FastApp Modification
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
