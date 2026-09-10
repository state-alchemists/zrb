from collections import deque
from collections.abc import Callable
from typing import Any


class Xcom(deque):
    """A cross-task message queue, reachable as `ctx.xcom[task_name]`.

    One task pushes a value, another pops it. This is the supported way to move
    data between tasks: a task's return value is pushed onto its own queue
    automatically, so a downstream task reads it with
    `ctx.xcom["upstream-task"].pop()`.

    Two usage styles share one object, which is worth keeping straight:

    * **Queue** — `push`/`pop`/`peek`. `pop` takes the *oldest* value (FIFO),
      matching `peek`.
    * **Single variable** — `set`/`get`. `set` discards everything but the
      newest value, and `get` returns that newest value.

    Mixing them is what surprises people: after several `push` calls, `pop`
    returns the first value while `get` returns the last.

    Note `pop` is FIFO here, which deliberately differs from `deque.pop`. Use
    `popright` for the LIFO behaviour `deque.pop` normally has.
    """

    def __repr__(self):
        class_name = self.__class__.__name__
        return f"<{class_name} {list(self)}>"

    def append(self, value):
        """Add a value to the end of the queue and fire push callbacks."""
        super().append(value)
        self.__call_push_callbacks()

    def appendleft(self, value):
        """Add a value to the front of the queue and fire push callbacks."""
        super().appendleft(value)
        self.__call_push_callbacks()

    def extend(self, values):
        """Add every value to the end of the queue, firing push callbacks once."""
        super().extend(values)
        self.__call_push_callbacks()

    def extendleft(self, values):
        """Prepend every value (in reverse), firing push callbacks once."""
        super().extendleft(values)
        self.__call_push_callbacks()

    def insert(self, index, value):
        """Insert a value at *index*, firing push callbacks."""
        super().insert(index, value)
        self.__call_push_callbacks()

    def remove(self, value):
        """Remove the first matching value, firing pop callbacks."""
        super().remove(value)
        self.__call_pop_callbacks()

    def __setitem__(self, index, value):
        super().__setitem__(index, value)
        self.__call_push_callbacks()

    def push(self, value):
        """Add a value to the end of the queue. Alias of `append`."""
        self.append(value)

    def popleft(self):
        """Remove and return the oldest value, firing pop callbacks.

        Raises:
            IndexError: If the queue is empty.
        """
        value = super().popleft()
        self.__call_pop_callbacks()
        return value

    def pop(self):
        """Remove and return the oldest value. Alias of `popleft`.

        Overrides `deque.pop`, which removes from the right. Use `popright` for
        that behaviour.

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

    def peek(self):
        """Return the oldest value without removing it.

        The non-destructive counterpart of `pop`, so both see the same element.

        Raises:
            IndexError: If the queue is empty.
        """
        # Queue semantics: non-destructive `pop`. `pop()`/`popleft()` remove
        # from the left (oldest first), so `peek()` returns that same front
        # element without removing it.
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

        Pairs with `set` for single-variable use. Unlike `peek`, this never
        raises on an empty queue, and it reads the *newest* value rather than
        the oldest — so for a task that ran more than once (readiness
        monitoring re-executes it), this is the latest result.
        """
        # Single-variable semantics (paired with `set()`): return the current
        # value, i.e. the most recently pushed one. `set()` keeps only the
        # latest, so for set-based usage this is that single element; for a
        # plain-push task that ran more than once (readiness-monitored re-exec)
        # it is the latest result, not a stale earlier one.
        if len(self) > 0:
            return self[-1]
        return default_value

    def set(self, new_value: Any):
        """Replace the contents with a single value.

        Pairs with `get` for single-variable use: everything already queued is
        discarded, so the queue holds exactly `new_value`.
        """
        self.push(new_value)
        while len(self) > 1:
            self.pop()

    def append_push_callback(self, callback: Callable[[], Any]):
        """Register a zero-argument callback fired after every push.

        Callbacks run in registration order and receive nothing — read the
        queue itself for the value. Used to wake tasks waiting on this queue.
        """
        if not hasattr(self, "push_callbacks"):
            self.push_callbacks: list[Callable[[], Any]] = []
        self.push_callbacks.append(callback)

    def append_pop_callback(self, callback: Callable[[], Any]):
        """Register a zero-argument callback fired after every pop.

        Fires for `pop`, `popleft`, and `popright` alike.
        """
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
