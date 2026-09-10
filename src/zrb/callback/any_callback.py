from abc import ABC, abstractmethod
from typing import Any

from zrb.session.any_session import AnySession


class AnyCallback(ABC):
    @abstractmethod
    async def async_run(self, parent_session: AnySession, session: AnySession) -> Any:
        """Run this callback's task in its own session.

        Args:
            parent_session: Session that triggered the callback, whose inputs
                and xcom values are available to it.
            session: Fresh session the callback's own task runs in.

        Returns:
            The result of the callback's task.
        """
