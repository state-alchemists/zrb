from zrb.helper.typing import Any
from zrb.task.cmd_task import CmdTask
from zrb.task.decorator import python_task
from zrb.task.notifier import Notifier
from zrb.task.task import Task
from zrb.task_input.str_input import StrInput


def create_recurring_action(
    notif_title: str,
    trigger_caption: str,
    trigger_xcom_key: str,
    default_message: str = "👋",
) -> Task:
    # define inputs
    message_input = StrInput(
        name="message",
        default=default_message,
        prompt="Message to be shown",
    )
    command_input = StrInput(
        name="command",
        default="",
        prompt="Command to be executed",
    )
    # define tasks
    show_trigger_info = _create_show_trigger_info(
        trigger_caption=trigger_caption, trigger_xcom_key=trigger_xcom_key
    )
    run_command = CmdTask(
        name="run-command",
        icon="⚙️",
        color="blue",
        inputs=[command_input],
        upstreams=[show_trigger_info],
        should_execute='{{ input.command != "" }}',
        cmd="{{ input.command }}",
    )
    notify = Notifier(
        name="notify",
        icon="📢",
        color="green",
        inputs=[message_input],
        title=notif_title,
        message="{{ input.message }}",
        upstreams=[show_trigger_info],
        should_execute='{{ input.message != "" }}',
    )
    # return aggregator task
    return Task(
        name="recurring-action",
        inputs=[message_input, command_input],
        upstreams=[run_command, notify],
        retry=0,
    )


def _create_show_trigger_info(trigger_caption: str, trigger_xcom_key: str) -> Task:
    @python_task(
        name="show-trigger-info",
        icon="🔍",
        color="magenta",
    )
    def show_trigger_info(*args: Any, **kwargs: Any):
        task: Task = kwargs.get("_task")
        task.print_out(f"{trigger_caption}: {task.get_xcom(trigger_xcom_key)}")

    return show_trigger_info
