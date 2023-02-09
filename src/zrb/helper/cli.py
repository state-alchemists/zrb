from ..runner import runner
from .loader.load_module import load_module
from ..config.config import init_scripts, should_load_builtin
from .log import logger
from .accessories.color import colored

import click
import os


def create_cli() -> click.Group:
    cli = click.Group(name='zrb', help='Your faithful companion.')

    if 'PYTHONUNBUFFERED' not in os.environ:
        os.environ['PYTHONUNBUFFERED'] = '1'

    # load from ZRB_INIT_SCRIPTS environment
    for init_script in init_scripts:
        load_module(script_path=init_script)

    # Load default tasks
    if should_load_builtin:
        logger.info(colored('Loading builtins', attrs=['dark']))
        from .. import builtin
        assert builtin

    # Load zrb_init.py
    project_dir = os.getcwd()
    load_zrb_init(project_dir)

    # Serve all tasks registered to runner
    cli = runner.serve(cli)
    return cli


def load_zrb_init(project_dir: str):
    project_script = os.path.join(project_dir, 'zrb_init.py')
    if os.path.isfile(project_script):
        load_module(script_path=project_script)
        os.environ['ZRB_PROJECT_DIR'] = project_dir
        logger.info(colored(f'ZRB_PROJECT_DIR={project_dir}', attrs=['dark']))
        add_project_dir_to_python_path(project_dir)
        python_path = os.getenv('PYTHONPATH')
        logger.info(colored(f'PYTHONPATH={python_path}', attrs=['dark']))
        return
    # zrb_init.py not found, look for it on the parent directory
    parent_project_dir = os.path.dirname(project_dir)
    if parent_project_dir == project_dir:
        # giving up, already on the root level directory
        logger.debug(colored('Cannot find zrb_init.py', attrs=['dark']))
        return
    # do the same thing again
    load_zrb_init(parent_project_dir)


def add_project_dir_to_python_path(project_dir: str):
    current_python_path = os.getenv('PYTHONPATH')
    if current_python_path is None or current_python_path == '':
        os.environ['PYTHONPATH'] = project_dir
        return
    os.environ['PYTHONPATH'] = ':'.join([
        current_python_path, project_dir
    ])
