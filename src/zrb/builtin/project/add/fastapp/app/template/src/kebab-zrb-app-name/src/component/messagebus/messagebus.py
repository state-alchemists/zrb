from abc import ABC, abstractmethod
from typing import Any, Callable, List, Mapping, Optional

from component.serializer.serializer import JsonSerializer, Serializer

TEventHandler = Callable[[Any], Any]


class Admin(ABC):
    @abstractmethod
    async def create_events(self, event_names: List[str]):
        pass

    @abstractmethod
    async def delete_events(self, event_names: List[str]):
        pass


class Publisher(ABC):
    @abstractmethod
    async def publish(self, event_name: str, message: Any):
        pass


class Consumer(ABC):
    @abstractmethod
    def register(self, event_name: str) -> Callable[[TEventHandler], Any]:
        pass

    @abstractmethod
    async def start(self):
        pass

    @abstractmethod
    async def stop(self):
        pass


class MessageSerializer:
    def __init__(self, serializers: Optional[Mapping[str, Serializer]] = None):
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
        return self.serializers.get(event_name, self.default_serializer)


def must_get_message_serializer(
    serializer: Optional[MessageSerializer] = None,
) -> MessageSerializer:
    if serializer is None:
        return MessageSerializer()
    return serializer
