import os

from zrb.builtin.project.monorepo._config import MONOREPO_CONFIG
from zrb.helper.util import to_kebab_case
from zrb.task.cmd_task import CmdTask
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
    retry=0
)

PULL_SUBREPO_UPSTREAM = _pull_monorepo
PUSH_SUBREPO_UPSTREAM = _pull_monorepo
for name, config in MONOREPO_CONFIG.items():
    kebab_name = to_kebab_case(name)
    subrepo_origin = config.get("origin", "")
    subrepo_folder = config.get("folder", "")
    subrepo_branch = config.get("branch", "main")

    # define pull subrepo
    pull_subrepo = CmdTask(
        name=f"pull-{kebab_name}",
        cmd=[
            f'if [ ! -d "{subrepo_folder}" ]',
            "then",
            "   echo run subtree add",
            f'  git subtree add --prefix "{subrepo_folder}" "{subrepo_origin}" "{subrepo_branch}"',  # noqa
            "fi",
            "echo run subtree pull",
            "set -e",
            f'git subtree pull --prefix "{subrepo_folder}" "{subrepo_origin}" "{subrepo_branch}"',  # noqa
        ],
        retry=0
    )
    PULL_SUBREPO_UPSTREAM >> pull_subrepo
    PULL_SUBREPO_UPSTREAM = pull_subrepo

    # define push subrepo
    push_subrepo = CmdTask(
        name=f"push-{kebab_name}",
        inputs=[StrInput(name="message", prompt="Commit Messsage", default="Save changes")],  # noqa
        cmd=[
            f'if [ ! -d "{subrepo_folder}" ]',
            "then",
            "   echo run subtree add",
            f'  git subtree add --prefix "{subrepo_folder}" "{subrepo_origin}" "{subrepo_branch}"',  # noqa
            "fi",
            "echo run subtree pull",
            "set -e",
            f'git subtree pull --prefix "{subrepo_folder}" "{subrepo_origin}" "{subrepo_branch}"',  # noqa
            "set +e",
            "git add . -A",
            'git commit -m "{{input.message}}"',
            f'git subtree push --prefix "{subrepo_folder}" "{subrepo_origin}" "{subrepo_branch}"',  # noqa
        ],
        retry=0
    )
    PUSH_SUBREPO_UPSTREAM >> push_subrepo
    PUSH_SUBREPO_UPSTREAM = push_subrepo