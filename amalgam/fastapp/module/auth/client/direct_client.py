from ..usecase import Usecase
from .base_client import BaseClient


class DirectClient(BaseClient):

    def __init__(self, usecase: Usecase):
        self.usecase = usecase

    async def greet(self, name: str) -> str:
        return self.usecase.greet(name)
