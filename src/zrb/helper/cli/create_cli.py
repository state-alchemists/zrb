from ...runner import runner
from ..loader.load_module import load_module
from ...config.config import init_scripts
import click
import os


def create_cli() -> click.Group:
    cli = click.Group(name='zrb', help='Your faithful sidekick.')

    # load from ZRB_INIT_SCRIPTS environment
    for init_script in init_scripts:
        load_module(script_path=init_script)

    # Load zrb_init.py
    project_script = os.path.join(os.getcwd(), 'zrb_init.py')
    if os.path.isfile(project_script):
        load_module(script_path=project_script)

    # Serve all tasks registered to runner
    cli = runner.serve(cli)
    return cli
