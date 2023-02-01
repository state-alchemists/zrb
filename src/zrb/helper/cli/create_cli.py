from ...runner import runner
from ..loader.load_module import load_module
from ...config.config import init_scripts, should_load_default
from ...default._register import register_default

import click
import os


def create_cli() -> click.Group:
    cli = click.Group(name='zrb', help='Your faithful companion.')

    # load from ZRB_INIT_SCRIPTS environment
    for init_script in init_scripts:
        load_module(script_path=init_script)

    # Load zrb_init.py
    project_script = os.path.join(os.getcwd(), 'zrb_init.py')
    if os.path.isfile(project_script):
        load_module(script_path=project_script)

    if should_load_default:
        register_default(runner)

    # Serve all tasks registered to runner
    cli = runner.serve(cli)
    return cli
