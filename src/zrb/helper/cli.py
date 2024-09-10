import os
import traceback
from functools import lru_cache

import click

from zrb.config.config import INIT_MODULES, INIT_SCRIPTS, SHOULD_LOAD_BUILTIN, VERSION
from zrb.helper.accessories.color import colored
from zrb.helper.loader.load_module import load_module
from zrb.helper.loader.load_script import load_script
from zrb.helper.log import logger
from zrb.helper.typecheck import typechecked
from zrb.runner import runner

logger.debug(colored("Loading zrb.helper.cli", attrs=["dark"]))

HELP = f"""
                bb
   zzzzz rr rr  bb
     zz  rrr  r bbbbbb
    zz   rr     bb   bb
   zzzzz rr     bbbbbb   {VERSION}
   _ _ . .  . _ .  _ . . .

Super framework for your super app.

☕ Donate at: https://stalchmst.com/donation
🐙 Submit issues/PR at: https://github.com/state-alchemists/zrb
🐤 Follow us at: https://twitter.com/zarubastalchmst
"""


class MultilineHelpClickGroup(click.Group):
    def format_help_text(self, ctx, formatter):
        formatter.write(self.help)


@lru_cache
@typechecked
def create_cli() -> click.Group:
    logger.info(colored("Prepare CLI", attrs=["dark"]))
    zrb_cli_group = MultilineHelpClickGroup(name="zrb", help=HELP)
    # Load default tasks
    if SHOULD_LOAD_BUILTIN:
        logger.info(colored("Load builtins", attrs=["dark"]))
        from zrb import builtin

        assert builtin
    # load from ZRB_INIT_MODULES
    for init_module in INIT_MODULES:
        try:
            load_module(init_module)
        except Exception:
            logger.error(
                colored(
                    f"Failed to load module {init_module}",
                    color="red",
                    attrs=["bold"],
                )
            )
    # Load zrb_init.py
    project_dir = os.getenv("ZRB_PROJECT_DIR", os.getcwd())
    project_script = os.path.join(project_dir, "zrb_init.py")
    load_script(script_path=project_script, sys_path_index=0)
    # load from ZRB_INIT_SCRIPTS environment
    for index, init_script in enumerate(INIT_SCRIPTS):
        logger.info(colored(f"Load module from {init_script}", attrs=["dark"]))
        try:
            load_script(script_path=init_script, sys_path_index=index + 1)
        except Exception:
            logger.error(
                colored(
                    f"Failed to load module from {init_script}",
                    color="red",
                    attrs=["bold"],
                )
            )
            traceback.print_exc()
    # Serve all tasks registered to runner
    logger.info(colored("Serve CLI", attrs=["dark"]))
    cli = runner.serve(zrb_cli_group)
    return cli
