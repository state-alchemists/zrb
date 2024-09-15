import os

from zrb.builtin.monorepo._config import PROJECT_DIR
from zrb.task.cmd_task import CmdTask
from zrb.task_env.env import Env
from zrb.task_input.any_input import AnyInput
from zrb.task_input.str_input import StrInput

_CURRENT_DIR = os.path.dirname(__file__)


def create_pull_monorepo_task(
    task_name: str = "pull-monorepo",
) -> CmdTask:
    return CmdTask(
        name=task_name,
        envs=[
            Env("TIME", os_name="", default="{{datetime.datetime.now()}}"),
        ],
        cmd_path=[
            os.path.join(_CURRENT_DIR, "_common.sh"),
            os.path.join(_CURRENT_DIR, "pull-monorepo.sh"),
        ],
        cwd=PROJECT_DIR,
        should_show_cmd=False,
        should_show_working_directory=False,
        should_print_cmd_result=False,
        retry=0,
    )


def create_push_monorepo_task(
    task_name: str = "push-monorepo", default_commit_message: str = "Save changes"
) -> CmdTask:
    return CmdTask(
        name=task_name,
        inputs=[_create_commit_message_input(default_commit_message)],
        envs=[
            Env("MESSAGE", os_name="", default="{{input.message}}"),
        ],
        cmd_path=[
            os.path.join(_CURRENT_DIR, "_common.sh"),
            os.path.join(_CURRENT_DIR, "push-monorepo.sh"),
        ],
        cwd=PROJECT_DIR,
        should_show_cmd=False,
        should_show_working_directory=False,
        should_print_cmd_result=False,
        retry=0,
    )


def create_add_subrepo_task(
    origin: str,
    folder: str,
    branch: str,
    task_name: str = "add",
) -> CmdTask:
    return CmdTask(
        name=task_name,
        envs=[
            Env("ORIGIN", os_name="", default=origin),
            Env("FOLDER", os_name="", default=folder),
            Env("BRANCH", os_name="", default=branch),
            Env("TIME", os_name="", default="{{datetime.datetime.now()}}"),
        ],
        cmd_path=[
            os.path.join(_CURRENT_DIR, "_common.sh"),
            os.path.join(_CURRENT_DIR, "add-subrepo.sh"),
        ],
        cwd=PROJECT_DIR,
        should_show_cmd=False,
        should_show_working_directory=False,
        should_print_cmd_result=False,
        retry=0,
    )


def create_pull_subrepo_task(
    origin: str,
    folder: str,
    branch: str,
    task_name: str = "pull",
) -> CmdTask:
    return CmdTask(
        name=task_name,
        envs=[
            Env("ORIGIN", os_name="", default=origin),
            Env("FOLDER", os_name="", default=folder),
            Env("BRANCH", os_name="", default=branch),
            Env("TIME", os_name="", default="{{datetime.datetime.now()}}"),
        ],
        cmd_path=[
            os.path.join(_CURRENT_DIR, "_common.sh"),
            os.path.join(_CURRENT_DIR, "pull-subrepo.sh"),
        ],
        cwd=PROJECT_DIR,
        should_show_cmd=False,
        should_show_working_directory=False,
        should_print_cmd_result=False,
        retry=0,
    )


def create_push_subrepo_task(
    origin: str,
    folder: str,
    branch: str,
    task_name: str = "push",
    default_commit_message: str = "Commit",
) -> CmdTask:
    return CmdTask(
        name=task_name,
        inputs=[_create_commit_message_input(default_commit_message)],
        envs=[
            Env("ORIGIN", os_name="", default=origin),
            Env("FOLDER", os_name="", default=folder),
            Env("BRANCH", os_name="", default=branch),
            Env("TIME", os_name="", default="{{datetime.datetime.now()}}"),
            Env("MESSAGE", os_name="", default="{{input.message}}"),
        ],
        cmd_path=[
            os.path.join(_CURRENT_DIR, "_common.sh"),
            os.path.join(_CURRENT_DIR, "push-subrepo.sh"),
        ],
        cwd=PROJECT_DIR,
        should_show_cmd=False,
        should_show_working_directory=False,
        should_print_cmd_result=False,
        retry=0,
    )


def _create_commit_message_input(default: str) -> AnyInput:
    return StrInput(
        name="message",
        shortcut="m",
        prompt="Commit Message",
        default=default,
    )
