from sqlalchemy import create_engine, Engine
from config import app_db_connection

engine: Engine = create_engine(app_db_connection, echo=True)
