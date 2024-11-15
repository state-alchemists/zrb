from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from ..config import APP_REPOSITORY_DB_URL

db_engine = create_async_engine(APP_REPOSITORY_DB_URL, echo=True)
# Create an async session factory
async_session = sessionmaker(
    db_engine, expire_on_commit=False, class_=AsyncSession
)
