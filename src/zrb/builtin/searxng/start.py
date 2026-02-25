import os
import shutil

from zrb.builtin.group import searxng_group
from zrb.config.config import CFG
from zrb.context.any_context import AnyContext
from zrb.input.int_input import IntInput
from zrb.task.cmd_task import CmdTask
from zrb.task.http_check import HttpCheck
from zrb.task.make_task import make_task


@make_task(
    name="copy-searxng-setting",
)
def copy_searxng_setting(ctx: AnyContext):
    dest_config_dir = os.path.abspath(
        os.path.join(os.path.expanduser("~"), ".config", "searxng")
    )
    dest_config_file = os.path.join(dest_config_dir, "settings.yml.new")
    if not os.path.isfile(dest_config_file):
        ctx.print(f"Creating Searxng config file")
        os.makedirs(dest_config_dir, exist_ok=True)
        src_config_file = os.path.join(
            os.path.dirname(__file__), "config", "settings.yml.new"
        )
        shutil.copy(src_config_file, dest_config_dir)
        ctx.print(f"Searxng config file created: {dest_config_file}")


start_searxng = searxng_group.add_task(
    CmdTask(
        name="start-searxng",
        input=IntInput(name="port", default=CFG.SEARXNG_PORT),
        upstream=copy_searxng_setting,
        cwd=os.path.expanduser("~"),
        cmd="docker run --rm -p {ctx.input.port}:8080 -v ./config/:/etc/searxng/ docker.io/searxng/searxng:latest -d",  # noqa
        readiness_check=HttpCheck(
            "check-searxng",
            url="http://localhost:{ctx.input.port}",
        ),
    ),
    alias="start",
)
