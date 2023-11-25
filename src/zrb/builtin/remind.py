from zrb.task.any_task import AnyTask
from zrb.task.triggered_task import TriggeredTask
from zrb.task.decorator import python_task
from zrb.task_input.str_input import StrInput
from zrb.runner import runner


@python_task(
    name='show-message',
    inputs=[
        StrInput(
            name='message',
            default='👋',
            prompt='Message',
            description='Message'
        ),
    ]
)
def _show_message(*args, **kwargs):
    task: AnyTask = kwargs['_task']
    task.print_out(kwargs.get('message', '👋'))


remind = TriggeredTask(
    name='remind',
    inputs=[
        StrInput(
            name='schedule',
            default='* * * * *',
            prompt='Schedule cron pattern (minute hour day(month) month day(week)',  # noqa
            description='Schedule cron pattern to show the message'
        ),
    ],
    schedule='{{input.schedule}}',
    task=_show_message
)
runner.register(remind)
