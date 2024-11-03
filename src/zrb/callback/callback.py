from typing import Any
from .any_callback import AnyCallback
from ..task.any_task import AnyTask
from ..attr.type import StrDictAttr
from ..util.attr import get_str_dict_attr
from ..session.any_session import AnySession


class Callback(AnyCallback):

    def __init__(
        self,
        name: str,
        input_mapping: StrDictAttr,
        task: AnyTask,
        queue_name: str | None = None,
        auto_render: bool = True,
    ):
        self._name = name
        self._input_mapping = input_mapping
        self._task = task
        self._queue_name = queue_name
        self._auto_render = auto_render

    @property
    def name(self) -> str:
        return self._name

    @property
    def queue_name(self) -> str:
        if self._queue_name is None:
            return self.name
        return self._queue_name

    async def async_run(self, session: AnySession) -> Any:
        inputs = get_str_dict_attr(
            session.shared_ctx, self._input_mapping, auto_render=self._auto_render
        )
        for name, value in inputs.items():
            session.shared_ctx.input[name] = value
        return await self._task.async_run(session)