from fastapp.common.base_usecase import BaseUsecase
from fastapp.module.anu.service.book.repository.factory import book_repository
from fastapp.module.anu.service.book.repository.repository import BookRepository
from fastapp.schema.book import BookCreate, BookResponse, BookUpdate


class BookUsecase(BaseUsecase):

    def __init__(self, book_repository: BookRepository):
        super().__init__()
        self.book_repository = book_repository

    @BaseUsecase.route(
        "/api/v1/books/{book_id}", methods=["get"], response_model=BookResponse
    )
    async def get_book_by_id(self, book_id: str) -> BookResponse:
        return await self.book_repository.get_by_id(book_id)

    @BaseUsecase.route(
        "/api/v1/books", methods=["get"], response_model=list[BookResponse]
    )
    async def get_all_books(self) -> list[BookResponse]:
        return await self.book_repository.get_all()

    @BaseUsecase.route(
        "/api/v1/books",
        methods=["post"],
        response_model=BookResponse | list[BookResponse],
    )
    async def create_book(
        self, data: BookCreate | list[BookCreate]
    ) -> BookResponse | list[BookResponse]:
        if isinstance(data, BookCreate):
            return await self.book_repository.create(data)
        return await self.book_repository.create_bulk(data)

    @BaseUsecase.route(
        "/api/v1/books/{book_id}", methods=["put"], response_model=BookResponse
    )
    async def update_book(self, book_id: str, data: BookUpdate) -> BookResponse:
        return await self.book_repository.update(book_id, data)

    @BaseUsecase.route(
        "/api/v1/books/{book_id}", methods=["delete"], response_model=BookResponse
    )
    async def delete_book(self, book_id: str) -> BookResponse:
        return await self.book_repository.delete(book_id)


book_usecase = BookUsecase(book_repository=book_repository)
