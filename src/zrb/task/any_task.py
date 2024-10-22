from abc import abstractmethod
from ..session.any_session import AnySession
from .any_base_task import AnyBaseTask


class AnyTask(AnyBaseTask):

    @abstractmethod
    async def async_exec_root_tasks(self, session: AnySession):
        pass

    @abstractmethod
    async def async_exec_chain(self, session: AnySession):
        pass
