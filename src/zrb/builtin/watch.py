from zrb.task.recurring_task import RecurringTask
from zrb.task.path_watcher import PathWatcher
from zrb.task_input.str_input import StrInput
from zrb.runner import runner
from zrb.builtin.helper.reccuring_action import create_recurring_action


watch = RecurringTask(
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
    triggers=[
        PathWatcher(name='watch-path', path='{{input.pattern}}')
    ],
    task=create_recurring_action(title='schedule')
)
runner.register(watch)
