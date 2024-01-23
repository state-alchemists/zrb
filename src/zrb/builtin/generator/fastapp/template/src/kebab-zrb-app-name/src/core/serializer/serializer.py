from abc import ABC, abstractmethod
from typing import Any, Callable

import jsons


class Serializer(ABC):
    @abstractmethod
    def encode(self, message: Any) -> Any:
        pass

    @abstractmethod
    def decode(self, message: Any) -> Any:
        pass


class CustomSerializer(Serializer):
    def __init__(self, encoder: Callable[[Any], Any], decoder: Callable[[Any], Any]):
        self.encoder = encoder
        self.decoder = decoder

    def encode(self, message: Any) -> Any:
        return self.encoder(message)

    def decode(self, encoded_message: Any) -> Any:
        return self.decoder(encoded_message)


class JsonSerializer(Serializer):
    def encode(self, message: Any) -> Any:
        return jsons.dumps(message).encode()

    def decode(self, encoded_message: Any) -> Any:
        return jsons.loads(encoded_message.decode())
