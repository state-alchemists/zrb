import os
import traceback
from functools import lru_cache

import click

from zrb.config.config import init_scripts, should_load_builtin, version
from zrb.helper.accessories.color import colored
from zrb.helper.loader.load_module import load_module
from zrb.helper.log import logger
from zrb.helper.typecheck import typechecked
from zrb.runner import runner

HELP = f"""
                bb
   zzzzz rr rr  bb
     zz  rrr  r bbbbbb
    zz   rr     bb   bb
   zzzzz rr     bbbbbb   {version}
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
    if should_load_builtin:
        logger.info(colored("Load builtins", attrs=["dark"]))
        from zrb import builtin

        assert builtin
    # Load zrb_init.py
    project_dir = os.getenv("ZRB_PROJECT_DIR", os.getcwd())
    project_script = os.path.join(project_dir, "zrb_init.py")
    load_module(script_path=project_script)
    # load from ZRB_INIT_SCRIPTS environment
    for init_script in init_scripts:
        logger.info(colored(f"Load module from {init_script}", attrs=["dark"]))
        try:
            load_module(script_path=init_script)
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
