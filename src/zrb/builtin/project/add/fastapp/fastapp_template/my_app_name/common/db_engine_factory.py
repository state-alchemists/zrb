from my_app_name.config import APP_DB_URL
from sqlmodel import create_engine

connect_args = {"check_same_thread": False}
db_engine = create_engine(APP_DB_URL, connect_args=connect_args, echo=True)
