from .runner import runner
from .module_loader import load_module
import click
import os


def create_cli() -> click.Group:
    # Create cli
    @click.group(name='zrb', help='Your faithful sidekick')
    def cli():
        pass

    # load from ZRB_INIT_SCRIPTS environment
    init_scripts = os.getenv('ZRB_INIT_SCRIPTS', '').split(':')
    for init_script in init_scripts:
        load_module(script_path=init_script)

    # Load zrb_init.py
    project_script = os.path.join(os.getcwd(), 'zrb_init.py')
    if os.path.isfile(project_script):
        load_module(script_path=project_script)

    # Serve all tasks registered to runner
    cli = runner.serve(cli)
    return cli
