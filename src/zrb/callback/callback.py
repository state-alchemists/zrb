from typing import Any

from zrb.attr.type import StrDictAttr
from zrb.callback.any_callback import AnyCallback
from zrb.session.any_session import AnySession
from zrb.task.any_task import AnyTask
from zrb.util.attr import get_str_dict_attr
from zrb.xcom.xcom import Xcom


class Callback(AnyCallback):
    def __init__(
        self,
        task: AnyTask,
        input_mapping: StrDictAttr,
        render_input_mapping: bool = True,
        inflight_queue: str | None = None,
    ):
        self._task = task
        self._input_mapping = input_mapping
        self._render_input_mapping = render_input_mapping
        self._inflight_queue = inflight_queue

    async def async_run(self, parent_session: AnySession, session: AnySession) -> Any:
        parent_xcom = parent_session.shared_ctx.xcom
        # publish to inflight queue
        if self._inflight_queue is not None:
            if self._inflight_queue not in parent_xcom:
                parent_xcom[self._inflight_queue] = Xcom([])
            parent_xcom[self._inflight_queue].push("")
        # prepare input and run
        inputs = get_str_dict_attr(
            session.shared_ctx,
            self._input_mapping,
            auto_render=self._render_input_mapping,
        )
        for name, value in inputs.items():
            session.shared_ctx.input[name] = value
        result = await self._task.async_run(session)
        # consume from inflight queue
        if self._inflight_queue is not None:
            parent_xcom[self._inflight_queue].pop()
        # return the result
        return result
