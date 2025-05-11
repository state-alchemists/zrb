from abc import ABC, abstractmethod
from typing import Any

from zrb.session.any_session import AnySession


class AnyCallback(ABC):
    @abstractmethod
    async def async_run(self, parent_session: AnySession, session: AnySession) -> Any:
        pass
