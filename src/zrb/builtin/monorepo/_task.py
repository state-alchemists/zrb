import os
from datetime import datetime

from zrb.builtin.monorepo._config import MONOREPO_CONFIG
from zrb.builtin.monorepo._group import monorepo_group
from zrb.helper.util import to_kebab_case
from zrb.runner import runner
from zrb.task.cmd_task import CmdTask
from zrb.task_group.group import Group
from zrb.task_input.str_input import StrInput

_PROJECT_DIR = os.getenv("ZRB_PROJECT_DIR", ".")

_pull_monorepo = CmdTask(
    name="pull-monorepo",
    inputs=[StrInput(name="message")],
    cwd=_PROJECT_DIR,
    cmd=[
        "git add . -A",
        'git commit -m "{{input.message}}"',
        'git pull origin "$(git branch --show-current)"',
    ],
    retry=0,
)

PULL_SUBREPO_UPSTREAM = _pull_monorepo
PUSH_SUBREPO_UPSTREAM = _pull_monorepo
for name, config in MONOREPO_CONFIG.items():
    kebab_name = to_kebab_case(name)
    group = Group(
        name=kebab_name, parent=monorepo_group, description=f"Subrepo {name} management"
    )
    subrepo_origin = config.get("origin", "")
    subrepo_folder = config.get("folder", "")
    subrepo_branch = config.get("branch", "main")

    # define pull subrepo
    pull_subrepo = CmdTask(
        name="pull",
        group=group,
        inputs=[
            StrInput(
                name="message",
                shortcut="m",
                prompt="Commit Messsage",
                default=lambda m: f"Pulling from subrepo at {datetime.now().strftime('%Y-%m-%d %I:%M:%p')}",  # noqa
            )
        ],
        cmd=[
            f'if [ ! -d "{subrepo_folder}" ]',
            "then",
            "   echo Run subtree add",
            f'  git subtree add --prefix "{subrepo_folder}" "{subrepo_origin}" "{subrepo_branch}"',  # noqa
            "fi",
            "echo Run subtree pull",
            "set -e",
            f'git subtree pull --prefix "{subrepo_folder}" "{subrepo_origin}" "{subrepo_branch}"',  # noqa
        ],
        retry=0,
    )
    _pull_monorepo >> pull_subrepo
    linked_pull_subrepo = pull_subrepo.copy()
    PULL_SUBREPO_UPSTREAM >> linked_pull_subrepo
    PULL_SUBREPO_UPSTREAM = linked_pull_subrepo
    runner.register(pull_subrepo)

    # define push subrepo
    push_subrepo = CmdTask(
        name="push",
        group=group,
        inputs=[
            StrInput(
                name="message",
                shortcut="m",
                prompt="Commit Messsage",
                default=lambda m: f"Pushing to subrepo at {datetime.now().strftime('%Y-%m-%d %I:%M:%p')}",  # noqa
            )
        ],
        cmd=[
            f'if [ ! -d "{subrepo_folder}" ]',
            "then",
            "   echo Run subtree add",
            f'  git subtree add --prefix "{subrepo_folder}" "{subrepo_origin}" "{subrepo_branch}"',  # noqa
            "fi",
            "echo Run subtree pull",
            "set -e",
            f'git subtree pull --prefix "{subrepo_folder}" "{subrepo_origin}" "{subrepo_branch}"',  # noqa
            "set +e",
            "git add . -A",
            'git commit -m "{{input.message}}"',
            f'git subtree push --prefix "{subrepo_folder}" "{subrepo_origin}" "{subrepo_branch}"',  # noqa
        ],
        retry=0,
    )
    _pull_monorepo >> push_subrepo
    linked_push_subrepo = push_subrepo.copy()
    PUSH_SUBREPO_UPSTREAM >> push_subrepo
    PUSH_SUBREPO_UPSTREAM = linked_push_subrepo
    runner.register(push_subrepo)
