from abc import ABC, abstractmethod
from module.auth.schema.token import TokenData


class TokenUtil(ABC):

    @abstractmethod
    def encode(self, token_data: TokenData) -> str:
        pass

    @abstractmethod
    def decode(self, token_str: str) -> TokenData:
        pass
