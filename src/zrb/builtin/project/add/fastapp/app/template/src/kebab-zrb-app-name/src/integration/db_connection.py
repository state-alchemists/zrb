import time

from config import (
    APP_DB_CONNECTION,
    APP_DB_ENGINE_SHOW_LOG,
    APP_DB_POOL_MAX_OVERFLOW,
    APP_DB_POOL_PRE_PING,
    APP_DB_POOL_SIZE,
)
from integration.log import logger
from sqlalchemy import Engine, create_engine, event


@event.listens_for(Engine, "before_cursor_execute")
def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    context._query_start_time = time.time()
    one_line_statement = " ".join(statement.split("\n"))
    logger.info(f"💽 [start query] SQL:`{one_line_statement}`, parameters {parameters}")


@event.listens_for(Engine, "after_cursor_execute")
def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    total = time.time() - context._query_start_time
    one_line_statement = " ".join(statement.split("\n"))
    logger.info(
        " ".join(
            [
                f"💽 [query completed] Elapsed time: {total} ms,",
                f"SQL: `{one_line_statement}`,",
                f"parameters {parameters}",
            ]
        )
    )


engine: Engine = create_engine(
    APP_DB_CONNECTION,
    echo=APP_DB_ENGINE_SHOW_LOG,
    pool_pre_ping=APP_DB_POOL_PRE_PING,
    pool_size=APP_DB_POOL_SIZE,
    max_identifier_length=APP_DB_POOL_MAX_OVERFLOW,
)
