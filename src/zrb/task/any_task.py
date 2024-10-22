from abc import abstractmethod
from ..session.any_session import AnySession
from .any_base_task import AnyBaseTask


class AnyTask(AnyBaseTask):

    @abstractmethod
    async def async_run_root_tasks(self, session: AnySession):
        pass

    @abstractmethod
    async def async_run_chain(self, session: AnySession):
        pass
