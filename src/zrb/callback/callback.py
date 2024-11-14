from typing import Any

from ..attr.type import StrDictAttr
from ..session.any_session import AnySession
from ..task.any_task import AnyTask
from ..util.attr import get_str_dict_attr
from .any_callback import AnyCallback


class Callback(AnyCallback):

    def __init__(
        self,
        input_mapping: StrDictAttr,
        task: AnyTask,
        auto_render: bool = True,
    ):
        self._input_mapping = input_mapping
        self._task = task
        self._auto_render = auto_render

    async def async_run(self, session: AnySession) -> Any:
        inputs = get_str_dict_attr(
            session.shared_ctx, self._input_mapping, auto_render=self._auto_render
        )
        for name, value in inputs.items():
            session.shared_ctx.input[name] = value
        return await self._task.async_run(session)
