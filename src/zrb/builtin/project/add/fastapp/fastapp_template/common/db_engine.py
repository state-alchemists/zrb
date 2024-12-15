from fastapp_template.config import APP_DB_URL
from sqlmodel import create_engine

connect_args = {"check_same_thread": False}
engine = create_engine(APP_DB_URL, connect_args=connect_args)
