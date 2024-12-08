from fastapp.common.base_db_repository import BaseDBRepository
from fastapp.common.error import NotFoundError
from fastapp.module.anu.service.book.repository.book_repository import (
    BookRepository,
)
from fastapp.schema.book import Book, BookCreate, BookResponse, BookUpdate
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import Session, select

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


class BookDBRepository(
    BaseDBRepository[Book, BookResponse, BookCreate, BookUpdate], BookRepository
):
    db_model = Book
    response_model = BookResponse
    create_model = BookCreate
    update_model = BookUpdate
    entity_name = "book"
    column_preprocessors = {}
