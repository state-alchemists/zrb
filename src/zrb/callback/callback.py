from typing import Any

from zrb.attr.type import StrDictAttr
from zrb.callback.any_callback import AnyCallback
from zrb.session.any_session import AnySession
from zrb.task.any_task import AnyTask
from zrb.util.attr import get_str_dict_attr
from zrb.util.string.conversion import to_snake_case
from zrb.xcom.xcom import Xcom


class Callback(AnyCallback):
    def __init__(
        self,
        task: AnyTask,
        input_mapping: StrDictAttr,
        render_input_mapping: bool = True,
        result_queue: str | None = None,
    ):
        self._task = task
        self._input_mapping = input_mapping
        self._render_input_mapping = render_input_mapping
        self._result_queue = result_queue

    async def async_run(self, parent_session: AnySession, session: AnySession) -> Any:
        # prepare input
        inputs = get_str_dict_attr(
            session.shared_ctx,
            self._input_mapping,
            auto_render=self._render_input_mapping,
        )
        for name, value in inputs.items():
            session.shared_ctx.input[name] = value
            session.shared_ctx.input[to_snake_case(name)] = value
        # run task and get result
        result = await self._task.async_run(session)
        self.publish_result(parent_session, result)
        return result

    def publish_result(self, parent_session: AnySession, result: Any):
        # publish to result queue
        parent_xcom = parent_session.shared_ctx.xcom
        if self._result_queue is not None:
            if self._result_queue not in parent_xcom:
                parent_xcom[self._result_queue] = Xcom([])
            parent_xcom[self._result_queue].push(result)
