from zrb.builtin._helper.reccuring_action import create_recurring_action
from zrb.runner import runner
from zrb.task.server import Controller, Server
from zrb.task.time_watcher import TimeWatcher
from zrb.task_input.str_input import StrInput

schedule = Server(
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
    controllers=[
        Controller(
            name="periodic",
            trigger=TimeWatcher(
                name="watch-time",
                color="cyan",
                icon="⏰",
                schedule="{{input.schedule}}",
            ),
            action=create_recurring_action(
                notif_title="Schedule",
            ),
        )
    ],
)
runner.register(schedule)
