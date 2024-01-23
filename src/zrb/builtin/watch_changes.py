from zrb.builtin.helper.reccuring_action import create_recurring_action
from zrb.runner import runner
from zrb.task.path_watcher import PathWatcher
from zrb.task.recurring_task import RecurringTask
from zrb.task_input.str_input import StrInput

watch_changes = RecurringTask(
    name="watch-changes",
    icon="🕵️",
    color="yellow",
    description="Watch changes and show message/run command",
    inputs=[
        StrInput(
            name="pattern",
            default="*.*",
            prompt="File pattern",
            description="File pattern to be watched",
        ),
        StrInput(
            name="ignored-pattern",
            default="",
            prompt="Ignored file pattern",
            description="Ignored file pattern",
        ),
    ],
    triggers=[
        PathWatcher(
            name="watch-path",
            color="cyan",
            icon="👀",
            path="{{input.pattern}}",
            ignored_path="{{input.ignored_pattern}}",
        )
    ],
    task=create_recurring_action(
        notif_title="Watch",
        trigger_caption="File changes",
        trigger_xcom_key="watch-path.file",
    ),
)
runner.register(watch_changes)
