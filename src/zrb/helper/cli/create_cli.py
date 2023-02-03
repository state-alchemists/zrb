from ...runner import runner
from ..loader.load_module import load_module
from ...config.config import init_scripts, should_load_default

import click
import logging
import os


def create_cli() -> click.Group:
    cli = click.Group(name='zrb', help='Your faithful companion.')

    if 'PYTHONUNBUFFERED' not in os.environ:
        os.environ['PYTHONUNBUFFERED'] = '1'

    # load from ZRB_INIT_SCRIPTS environment
    for init_script in init_scripts:
        load_module(script_path=init_script)

    # Load default tasks
    if should_load_default:
        from ... import default
        assert default

    # Load zrb_init.py
    try:
        project_dir = os.getcwd()
        load_zrb_init(project_dir)
    except Exception:
        logging.debug('Cannot find zrb_init.py')

    # Serve all tasks registered to runner
    cli = runner.serve(cli)
    return cli


def load_zrb_init(project_dir: str):
    project_script = os.path.join(project_dir, 'zrb_init.py')
    if os.path.isfile(project_script):
        load_module(script_path=project_script)
        os.environ['ZRB_PROJECT_DIR'] = project_dir
        return
    parent_project_dir = os.path.dirname(project_dir)
    if parent_project_dir == project_dir:
        return
    load_zrb_init(parent_project_dir)
