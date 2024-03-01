from abc import ABC, abstractmethod
from typing import Any, Callable, List, Mapping, TypeVar

TRPCHandler = Callable[..., Any]
TMessage = TypeVar("TMessage", bound="Message")
TResult = TypeVar("TResult", bound="Result")


class Caller(ABC):
    @abstractmethod
    async def call(self, rpc_name: str, *args: Any, **kwargs: Any) -> Any:
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


class Message:
    def __init__(self, reply_event: str, args: List[Any], kwargs: Mapping[str, Any]):
        self.reply_event = reply_event
        self.args = args
        self.kwargs = kwargs

    def to_dict(self):
        return {
            "args": self.args,
            "kwargs": self.kwargs,
            "reply_event": self.reply_event,
        }

    @classmethod
    def from_dict(cls, dictionary: Mapping[str, Any]) -> TMessage:
        return cls(
            reply_event=dictionary.get("reply_event", ""),
            args=dictionary.get("args", []),
            kwargs=dictionary.get("kwargs", {}),
        )


class Result:
    def __init__(self, result: Any = None, error: str = ""):
        self.result = result
        self.error = error

    def to_dict(self):
        return {"result": self.result, "error": self.error}

    @classmethod
    def from_dict(cls, dictionary: Mapping[str, Any]) -> TResult:
        return cls(
            result=dictionary.get("result", None), error=dictionary.get("error", "")
        )
