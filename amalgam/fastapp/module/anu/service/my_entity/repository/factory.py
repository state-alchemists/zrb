from fastapp.common.db_engine import engine
from fastapp.config import APP_REPOSITORY_TYPE
from fastapp.module.anu.service.book.repository.book_db_repository import (
    BookDBRepository,
)
from fastapp.module.anu.service.book.repository.book_repository import (
    BookRepository,
)

if APP_REPOSITORY_TYPE == "db":
    book_repository: BookRepository = BookDBRepository(engine)
else:
    book_repository: BookRepository = None
