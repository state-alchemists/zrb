from sqlalchemy import create_engine, Engine
from config import app_db_connection, app_db_engine_show_log

engine: Engine = create_engine(app_db_connection, echo=app_db_engine_show_log)
