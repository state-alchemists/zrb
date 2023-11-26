from zrb.task.triggered_task import TriggeredTask
from zrb.task.cmd_task import CmdTask
from zrb.task_input.str_input import StrInput
from zrb.runner import runner


watch = TriggeredTask(
    name='watch',
    description='Watch changes and show message/run command',
    inputs=[
        StrInput(
            name='pattern',
            default='*.*',
            prompt='File pattern',
            description='File pattern to be watched'
        ),
    ],
    watched_path='{{input.pattern}}',
    task=CmdTask(
        name='run-task',
        inputs=[
            StrInput(
                name='message',
                default='👋',
                prompt='Message to be shown',
                description='Message to be shown when changes detected'
            ),
            StrInput(
                name='command',
                default='',
                prompt='Command to be executed',
                description='Command to be executed when changes detected'
            ),
        ],
        cmd=[
            '{% if input.message != "" %}echo {{ input.message }}{% endif %}',
            '{% if input.command != "" %}{{ input.command }}{% endif %}',
        ]
    )
)
runner.register(watch)
