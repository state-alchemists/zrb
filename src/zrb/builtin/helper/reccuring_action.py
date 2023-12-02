from zrb.task.task import Task
from zrb.task.cmd_task import CmdTask
from zrb.task.notifier import Notifier
from zrb.task_input.str_input import StrInput


def create_recurring_action(title: str) -> Task:
    # define inputs
    message_input = StrInput(
        name='message',
        default='👋',
        prompt='Message to be shown',
    )
    command_input = StrInput(
        name='command',
        default='',
        prompt='Command to be executed',
    )
    # define tasks
    run_command = CmdTask(
        name='run-command',
        inputs=[command_input],
        should_execute='{{ input.command != "" }}'
    )
    notify = Notifier(
        name='notify',
        inputs=[message_input],
        title=title,
        message='{{ input.message }}',
        should_execute='{{ input.message != "" }}',
    )
    # return aggregator task
    return Task(
        name='recurring-action',
        inputs=[message_input, command_input],
        upstreams=[run_command, notify],
        retry=0
    )
