from zrb.task.triggered_task import TriggeredTask
from zrb.task.cmd_task import CmdTask
from zrb.task_input.str_input import StrInput
from zrb.runner import runner


schedule = TriggeredTask(
    name='schedule',
    description='Show message/run command periodically',
    inputs=[
        StrInput(
            name='schedule',
            default='* * * * *',
            prompt='Schedule cron pattern (minute hour day(month) month day(week)',  # noqa
            description='Schedule cron pattern to show the message'
        ),
    ],
    schedule='{{input.schedule}}',
    task=CmdTask(
        name='run-task',
        inputs=[
            StrInput(
                name='message',
                default='👋',
                prompt='Message to be shown',
                description='Message to be shown on schedule'
            ),
            StrInput(
                name='command',
                default='',
                prompt='Command to be executed',
                description='Command to be executed on schedule'
            ),
        ],
        cmd=[
            '{% if input.message != "" %}echo {{ input.message }}{% endif %}',
            '{% if input.command != "" %}{{ input.command }}{% endif %}',
        ]
    )
)
runner.register(schedule)
