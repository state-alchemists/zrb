from zrb.task.triggered_task import TriggeredTask
from zrb.task.cmd_task import CmdTask
from zrb.task_input.str_input import StrInput
from zrb.runner import runner


watch = TriggeredTask(
    name='watch',
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
        name='run-command',
        inputs=[
            StrInput(
                name='command',
                default='echo "change detected"',
                prompt='Command to be executed',
                description='Command to be executed when changes detected'
            ),
        ],
        cmd='{{input.command}}'
    )
)
runner.register(watch)
