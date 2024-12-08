from abc import ABC, abstractmethod

from fastapp.schema.book import Book, BookCreate, BookResponse, BookUpdate


class BookRepository(ABC):

    @abstractmethod
    async def create(self, book_data: BookCreate) -> BookResponse:
        pass

    @abstractmethod
    async def get_by_id(self, book_id: str) -> Book:
        pass

    @abstractmethod
    async def get_all(self) -> list[Book]:
        pass

    @abstractmethod
    async def update(self, book_id: str, book_data: BookUpdate) -> Book:
        pass

    @abstractmethod
    async def delete(self, book_id: str) -> Book:
        pass

    @abstractmethod
    async def create_bulk(self, book_data_list: list[BookCreate]) -> list[BookResponse]:
        pass
