from alembic.migration import MigrationContext
from alembic.autogenerate import produce_migrations
from alembic.operations.ops import ModifyTableOps
from alembic.operations import Operations
from sqlalchemy import Engine
from sqlalchemy.orm import DeclarativeBase


def migrate(engine: Engine, Base: DeclarativeBase):
    migration_context = MigrationContext.configure(engine.connect())
    migration_script = produce_migrations(
        context=migration_context,
        metadata=Base.metadata
    )
    operations = Operations(migration_context)
    use_batch = engine.name == "sqlite"

    stack = [migration_script.upgrade_ops]
    while stack:
        elem = stack.pop(0)

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
