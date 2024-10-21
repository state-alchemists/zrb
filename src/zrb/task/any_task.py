from abc import abstractmethod
from ..session.any_session import AnySession
from .any_base_task import AnyBaseTask


class AnyTask(AnyBaseTask):

    @abstractmethod
    async def _async_run_with_downstreams(self, session: AnySession):
        pass
