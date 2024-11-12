from module.library.client.base_client import BaseClient
from module.library.usecase import Usecase


class DirectClient(BaseClient):

    def __init__(self, usecase: Usecase):
        self.usecase = usecase

    async def greet(self, name: str) -> str:
        return self.usecase.greet(name)
