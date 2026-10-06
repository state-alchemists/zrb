from collections import deque
from collections.abc import Callable, Iterable
from typing import Any, SupportsIndex


class Xcom(deque[Any]):
    """A cross-task message queue, reachable as `ctx.xcom[task_name]`.

    A task's return value is pushed onto its own queue, so a downstream task
    reads it with `ctx.xcom["upstream-task"].pop()`.

    * **Queue** — `push`/`pop`/`peek`. `pop` takes the *oldest* value (FIFO,
      unlike `deque.pop`; use `popright` for LIFO).
    * **Single variable** — `set`/`get`. `set` keeps only the new value, and
      `get` returns the newest value.
    """

    def __repr__(self) -> str:
        class_name = self.__class__.__name__
        return f"<{class_name} {list(self)}>"

    def append(self, value: Any) -> None:
        """Add a value to the end of the queue and fire push callbacks."""
        super().append(value)
        self.__call_push_callbacks()

    def appendleft(self, value: Any) -> None:
        """Add a value to the front of the queue and fire push callbacks."""
        super().appendleft(value)
        self.__call_push_callbacks()

    def extend(self, values: Iterable[Any]) -> None:
        """Add every value to the end of the queue, firing push callbacks once."""
        super().extend(values)
        self.__call_push_callbacks()

    def extendleft(self, values: Iterable[Any]) -> None:
        """Prepend every value (in reverse), firing push callbacks once."""
        super().extendleft(values)
        self.__call_push_callbacks()

    def insert(self, index: int, value: Any) -> None:
        """Insert a value at *index*, firing push callbacks."""
        super().insert(index, value)
        self.__call_push_callbacks()

    def remove(self, value: Any) -> None:
        """Remove the first matching value, firing pop callbacks."""
        super().remove(value)
        self.__call_pop_callbacks()

    def __setitem__(self, index: "SupportsIndex | slice", value: Any) -> None:
        # `deque.__setitem__` is two overloads -- (SupportsIndex, value) and
        # (slice, iterable) -- which no single forwarding call can satisfy.
        super().__setitem__(index, value)  # pyright: ignore[reportArgumentType]
        self.__call_push_callbacks()

    def push(self, value: Any) -> None:
        """Add a value to the end of the queue. Alias of `append`."""
        self.append(value)

    def popleft(self) -> Any:
        """Remove and return the oldest value, firing pop callbacks.

        Raises:
            IndexError: If the queue is empty.
        """
        value = super().popleft()
        self.__call_pop_callbacks()
        return value

    def pop(self) -> Any:
        """Remove and return the oldest value. Alias of `popleft`.

        Raises:
            IndexError: If the queue is empty.
        """
        return self.popleft()

    def popright(self) -> Any:
        """Remove and return the newest value, firing pop callbacks.

        Raises:
            IndexError: If the queue is empty.
        """
        value = super().pop()
        self.__call_pop_callbacks()
        return value

    def peek(self) -> Any:
        """Return the oldest value (what `pop` would return) without removing it.

        Raises:
            IndexError: If the queue is empty.
        """
        if len(self) > 0:
            return self[0]
        else:
            raise IndexError(
                "Xcom is empty: peek()/pop() need a prior push() or the task's "
                "own return value. Check the upstream task actually ran and "
                "produced a value before reading it here."
            )

    def get(self, default_value: Any = None) -> Any:
        """Return the newest value without removing it, or `default_value`.

        Pairs with `set`. For a task that ran more than once (readiness
        monitoring re-executes it), this is the latest result.
        """
        if len(self) > 0:
            return self[-1]
        return default_value

    def set(self, new_value: Any) -> None:
        """Replace the contents with a single value. Pairs with `get`."""
        self.push(new_value)
        while len(self) > 1:
            self.pop()

    def append_push_callback(self, callback: Callable[[], Any]) -> None:
        """Register a zero-argument callback fired after every push.

        Callbacks run in registration order; read the queue for the value.
        """
        if not hasattr(self, "push_callbacks"):
            self.push_callbacks: list[Callable[[], Any]] = []
        self.push_callbacks.append(callback)

    def append_pop_callback(self, callback: Callable[[], Any]) -> None:
        """Register a zero-argument callback fired after every pop.

        Fires for `pop`, `popleft`, and `popright` alike.
        """
        if not hasattr(self, "pop_callbacks"):
            self.pop_callbacks: list[Callable[[], Any]] = []
        self.pop_callbacks.append(callback)

    def __call_push_callbacks(self) -> None:
        if not hasattr(self, "push_callbacks"):
            return
        for callback in self.push_callbacks:
            callback()

    def __call_pop_callbacks(self) -> None:
        if not hasattr(self, "pop_callbacks"):
            return
        for callback in self.pop_callbacks:
            callback()
