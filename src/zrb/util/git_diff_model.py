from pydantic import BaseModel


class DiffResult(BaseModel):
    created: list[str]
    removed: list[str]
    updated: list[str]
