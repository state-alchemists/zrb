from datetime import datetime

from zrb.builtin.monorepo._config import PROJECT_DIR
from zrb.builtin.monorepo._group import monorepo_group
from zrb.builtin.monorepo._task import PUSH_SUBREPO_UPSTREAM
from zrb.runner import runner
from zrb.task.cmd_task import CmdTask
from zrb.task.task import Task
from zrb.task_input.str_input import StrInput

_push_monorepo = CmdTask(
    name="push-monorepo",
    inputs=[StrInput(name="message")],
    cmd=[
        "git add . -A",
        'git commit -m "{{input.message}}"',
        'git push origin "$(git branch --show-current)"',
    ],
    cwd=PROJECT_DIR,
    retry=0,
)

push_to_monorepo = Task(
    name="push",
    group=monorepo_group,
    description="Pushing to subrepos",
    inputs=[
        StrInput(
            name="message",
            shortcut="m",
            prompt="Commit Messsage",
            default=lambda m: f"Pushing to subrepos at {datetime.now().strftime('%Y-%m-%d %I:%M:%p')}",  # noqa
        )
    ],
)
PUSH_SUBREPO_UPSTREAM >> _push_monorepo >> push_to_monorepo
runner.register(push_to_monorepo)
