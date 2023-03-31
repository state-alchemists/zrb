from typing import Any, Callable, List, Mapping, TypeVar
from abc import ABC, abstractmethod

TRPCHandler = Callable[..., Any]
TMessage = TypeVar('TMessage', bound='Message')


class Caller(ABC):
    @abstractmethod
    def call(self, rpc_name: str, *args: Any, **kwargs: Any):
        pass


class Server(ABC):
    @abstractmethod
    def register(self, rpc_name: str) -> Callable[[TRPCHandler], Any]:
        pass

    @abstractmethod
    def start(self):
        pass

    @abstractmethod
    def stop(self):
        pass


class Message():
    def __init__(
        self,
        rpc_name: str,
        args: List[Any],
        kwargs: Mapping[str, Any],
        reply_event: str
    ):
        self.rpc_name = rpc_name
        self.args = args
        self.kwargs = kwargs
        self.reply_event = reply_event

    def to_dict(self):
        return {
            'rpc_name': self.rpc_name,
            'args': self.args,
            'kwargs': self.kwargs,
            'reply_event': self.reply_event
        }

    @classmethod
    def from_dict(cls, dictionary: Mapping[str, Any]) -> TMessage:
        return cls(
            rpc_name=dictionary.get('rpc_name', ''),
            args=dictionary.get('args', []),
            kwargs=dictionary.get('kwargs', {}),
            reply_event=dictionary.get('reply_event', ''),
        )
