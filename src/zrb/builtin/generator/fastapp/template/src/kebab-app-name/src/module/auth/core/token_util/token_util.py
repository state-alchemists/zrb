from abc import ABC, abstractmethod
from module.auth.schema.token import AccessTokenData, RefreshTokenData


class AccessTokenUtil(ABC):

    @abstractmethod
    def encode(self, token_data: AccessTokenData) -> str:
        pass

    @abstractmethod
    def decode(self, token_str: str) -> AccessTokenData:
        pass


class RefreshTokenUtil(ABC):

    @abstractmethod
    def encode(self, token_data: RefreshTokenData) -> str:
        pass

    @abstractmethod
    def decode(self, token_str: str) -> RefreshTokenData:
        pass
