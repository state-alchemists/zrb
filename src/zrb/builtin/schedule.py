from zrb.builtin.helper.reccuring_action import create_recurring_action
from zrb.runner import runner
from zrb.task.recurring_task import RecurringTask
from zrb.task.time_watcher import TimeWatcher
from zrb.task_input.str_input import StrInput

schedule = RecurringTask(
    name="schedule",
    icon="📅",
    color="yellow",
    description="Show message/run command periodically",
    inputs=[
        StrInput(
            name="schedule",
            default="* * * * *",
            prompt="Schedule cron pattern (minute hour day(month) month day(week)",  # noqa
            description="Schedule cron pattern to show the message",
        ),
    ],
    triggers=[
        TimeWatcher(
            name="watch-time", color="cyan", icon="⏰", schedule="{{input.schedule}}"
        )
    ],
    task=create_recurring_action(
        notif_title="Schedule",
        trigger_caption="Schedule",
        trigger_xcom_key="watch-time.scheduled-time",
    ),
)
runner.register(schedule)
