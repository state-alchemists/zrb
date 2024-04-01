from alembic.autogenerate import produce_migrations
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.operations.ops import ModifyTableOps
from sqlalchemy import Engine
from sqlalchemy.orm import DeclarativeBase


async def migrate(engine: Engine, Base: DeclarativeBase):
    """
    Generate migration and run it
    See: https://alembic.sqlalchemy.org/en/latest/cookbook.html#run-alembic-operation-objects-directly-as-in-from-autogenerate  # noqa
    """
    connection = engine.connect()
    migration_context = MigrationContext.configure(connection)
    migration_script = produce_migrations(
        context=migration_context, metadata=Base.metadata
    )
    operations = Operations(migration_context)
    use_batch = engine.name == "sqlite"

    stack = [migration_script.upgrade_ops]
    while stack:
        elem = stack.pop(0)
        if hasattr(elem, "table_name") and elem.table_name not in Base.metadata.tables:
            # We want the migration leave all unrelated tables as is
            continue

        if use_batch and isinstance(elem, ModifyTableOps):
            with operations.batch_alter_table(
                elem.table_name, schema=elem.schema
            ) as batch_ops:
                for table_elem in elem.ops:
                    # work around Alembic issue #753 (fixed in 1.5.0)
                    if hasattr(table_elem, "column"):
                        table_elem.column = table_elem.column.copy()
                    batch_ops.invoke(table_elem)
        elif hasattr(elem, "ops"):
            stack.extend(elem.ops)
        else:
            # work around Alembic issue #753 (fixed in 1.5.0)
            if hasattr(elem, "column"):
                elem.column = elem.column.copy()
            operations.invoke(elem)
    connection.commit()
    connection.close()
