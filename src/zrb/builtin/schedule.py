from zrb.task.recurring_task import RecurringTask
from zrb.task.time_watcher import TimeWatcher
from zrb.task_input.str_input import StrInput
from zrb.runner import runner
from zrb.builtin.helper.reccuring_action import create_recurring_action


schedule = RecurringTask(
    name='schedule',
    icon='📅',
    color='yellow',
    description='Show message/run command periodically',
    inputs=[
        StrInput(
            name='schedule',
            default='* * * * *',
            prompt='Schedule cron pattern (minute hour day(month) month day(week)',  # noqa
            description='Schedule cron pattern to show the message'
        ),
    ],
    triggers=[
        TimeWatcher(
            name='watch-schedule',
            color='cyan',
            icon='⏰',
            schedule='{{input.schedule}}'
        )
    ],
    task=create_recurring_action(
        title='Schedule',
        default_message='{{datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}}',  # noqa
    )
)
runner.register(schedule)
