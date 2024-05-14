from zrb.builtin._helper.reccuring_action import create_recurring_action
from zrb.runner import runner
from zrb.task.path_watcher import PathWatcher
from zrb.task.server import Controller, Server
from zrb.task_input.str_input import StrInput

watch_changes = Server(
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
    controllers=[
        Controller(
            name="watch",
            trigger=PathWatcher(
                name="watch-path",
                color="cyan",
                icon="👀",
                path="{{input.pattern}}",
                ignored_path="{{input.ignored_pattern}}",
            ),
            action=create_recurring_action(
                notif_title="Watch",
            ),
        )
    ],
)
runner.register(watch_changes)
