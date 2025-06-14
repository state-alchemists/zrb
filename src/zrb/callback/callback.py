import traceback
from typing import Any

from zrb.attr.type import StrDictAttr
from zrb.callback.any_callback import AnyCallback
from zrb.session.any_session import AnySession
from zrb.task.any_task import AnyTask
from zrb.util.attr import get_str_dict_attr
from zrb.util.cli.style import stylize_faint
from zrb.util.string.conversion import to_snake_case
from zrb.xcom.xcom import Xcom


class Callback(AnyCallback):
    """
    Represents a callback that runs a task after a trigger or scheduler event.

    It handles input mapping and can publish results and session names
    back to the parent session via XCom.
    """

    def __init__(
        self,
        task: AnyTask,
        input_mapping: StrDictAttr,
        render_input_mapping: bool = True,
        result_queue: str | None = None,
        error_queue: str | None = None,
        session_name_queue: str | None = None,
    ):
        """
        Initializes a new instance of the Callback class.

        Args:
            task: The task to be executed by the callback.
            input_mapping: A dictionary or attribute mapping to prepare inputs for the task.
            render_input_mapping: Whether to render the input mapping using
                f-string like syntax.
            result_queue: The name of the XCom queue in the parent session
                to publish the task result.
            result_queue: The name of the Xcom queue in the parent session
                to publish the task error.
            session_name_queue: The name of the XCom queue in the parent
                session to publish the session name.
        """
        self._task = task
        self._input_mapping = input_mapping
        self._render_input_mapping = render_input_mapping
        self._result_queue = result_queue
        self._error_queue = error_queue
        self._session_name_queue = session_name_queue

    async def async_run(self, parent_session: AnySession, session: AnySession) -> Any:
        self._maybe_publish_session_name_to_parent_session(
            parent_session=parent_session, session=session
        )
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
        try:
            result = await self._task.async_run(session)
            self._maybe_publish_result_to_parent_session(parent_session, result)
            return result
        except BaseException as e:
            ctx = session.get_ctx(self._task)
            ctx.print(traceback.format_exc())
            self._maybe_publish_error_to_parent_session(parent_session, e)

    def _maybe_publish_session_name_to_parent_session(
        self, parent_session: AnySession, session: AnySession
    ):
        self._maybe_publish_to_parent_session(
            parent_session=parent_session,
            xcom_name=self._session_name_queue,
            value=session.name,
        )

    def _maybe_publish_error_to_parent_session(
        self, parent_session: AnySession, error: Any
    ):
        self._maybe_publish_to_parent_session(
            parent_session=parent_session, xcom_name=self._error_queue, value=error
        )

    def _maybe_publish_result_to_parent_session(
        self, parent_session: AnySession, result: Any
    ):
        self._maybe_publish_to_parent_session(
            parent_session=parent_session, xcom_name=self._result_queue, value=result
        )

    def _maybe_publish_to_parent_session(
        self, parent_session: AnySession, xcom_name: str | None, value: Any
    ):
        if xcom_name is None:
            return
        parent_xcom = parent_session.shared_ctx.xcom
        if xcom_name not in parent_xcom:
            parent_xcom[xcom_name] = Xcom([])
        parent_xcom[xcom_name].push(value)
