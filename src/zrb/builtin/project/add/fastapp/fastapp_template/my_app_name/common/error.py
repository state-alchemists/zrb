from typing import Dict

from fastapi import HTTPException


class NotFoundError(HTTPException):
    def __init__(self, message: str, headers: Dict[str, str] | None = None) -> None:
        super().__init__(404, {"message": message}, headers)


class InvalidValueError(HTTPException):
    def __init__(self, message: str, headers: Dict[str, str] | None = None) -> None:
        super().__init__(422, {"message": message}, headers)


class ClientAPIError(HTTPException):
    def __init__(
        self, status_code: int, message: str, headers: Dict[str, str] | None = None
    ) -> None:
        super().__init__(status_code, {"message": message}, headers)
