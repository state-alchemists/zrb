from typing import Any, Callable, Mapping, Optional
from abc import ABC, abstractmethod
from core.serializer.serializer import Serializer, JsonSerializer

THandler = Callable[[Any], Any]


class Publisher(ABC):
    @abstractmethod
    def publish(self, event_name: str, message: Any):
        pass


class Consumer(ABC):
    @abstractmethod
    def register(self, event_name: str) -> Callable[[THandler], Any]:
        pass

    @abstractmethod
    def run(self):
        pass


class MessageSerializer():
    def __init__(
        self,
        serializers: Optional[Mapping[str, Serializer]] = None
    ):
        serializers = serializers if serializers is not None else {}
        self.serializers: Mapping[str, Serializer] = serializers
        self.default_serializer = JsonSerializer()

    def encode(self, event_name: str, message: Any) -> Any:
        serializer = self._get_serializer(event_name)
        return serializer.encode(message)

    def decode(self, event_name: str, encoded_message: Any) -> Any:
        serializer = self._get_serializer(event_name)
        return serializer.decode(encoded_message)

    def _get_serializer(self, event_name: str) -> Serializer:
        return self.serializers.get(
            event_name, self.default_serializer
        )


def get_message_serializer(
    serializer: Optional[MessageSerializer] = None
) -> MessageSerializer:
    if serializer is None:
        return MessageSerializer()
    return serializer
