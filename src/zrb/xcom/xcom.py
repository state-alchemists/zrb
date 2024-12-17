from collections import deque
from collections.abc import Callable
from typing import Any


class Xcom(deque):
    def __repr__(self):
        class_name = self.__class__.__name__
        return f"<{class_name} {list(self)}>"

    def append(self, value):
        super().append(value)
        self.__call_push_callbacks()

    def push(self, value):
        self.append(value)

    def popleft(self):
        value = super().popleft()
        self.__call_pop_callbacks()
        return value

    def pop(self):
        return self.popleft()

    def popright(self) -> Any:
        value = super().pop()
        self.__call_pop_callbacks()
        return value

    def peek(self):
        if len(self) > 0:
            return self[0]
        else:
            raise IndexError("Xcom is empty")

    def add_push_callback(self, callback: Callable[[], Any]):
        if not hasattr(self, "push_callbacks"):
            self.push_callbacks: list[Callable[[], Any]] = []
        self.push_callbacks.append(callback)

    def add_pop_callback(self, callback: Callable[[], Any]):
        if not hasattr(self, "pop_callbacks"):
            self.pop_callbacks: list[Callable[[], Any]] = []
        self.pop_callbacks.append(callback)

    def __call_push_callbacks(self):
        if not hasattr(self, "push_callbacks"):
            return
        for callback in self.push_callbacks:
            callback()

    def __call_pop_callbacks(self):
        if not hasattr(self, "pop_callbacks"):
            return
        for callback in self.pop_callbacks:
            callback()
