from typing import Dict

from fastapi import HTTPException


class NotFoundError(HTTPException):
    def __init__(self, message: str, headers: Dict[str, str] | None = None) -> None:
        super().__init__(404, {"message": message}, headers)
