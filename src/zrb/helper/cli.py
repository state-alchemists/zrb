from ..runner import runner
from .loader.load_module import load_module
from ..config.config import init_scripts, should_load_builtin
from .log import logger
from .accessories.color import colored

import click
import os
import sys


def create_cli() -> click.Group:
    cli = click.Group(name='zrb', help='Your faithful companion.')

    # load from ZRB_INIT_SCRIPTS environment
    for init_script in init_scripts:
        load_module(script_path=init_script)

    # Load default tasks
    if should_load_builtin:
        logger.info(colored('Load builtins', attrs=['dark']))
        from .. import builtin
        assert builtin

    # Load zrb_init.py
    project_dir = os.getenv('ZRB_PROJECT_DIR', os.getcwd())
    _load_zrb_init(project_dir)

    # Serve all tasks registered to runner
    cli = runner.serve(cli)
    return cli


def _load_zrb_init(project_dir: str):
    project_script = os.path.join(project_dir, 'zrb_init.py')
    if not os.path.isfile(project_script):
        return
    sys.path.append(project_dir)
    python_path = _get_new_python_path(project_dir)
    logger.info(colored(f'Set PYTHONPATH to {python_path}', attrs=['dark']))
    os.environ['PYTHONPATH'] = python_path
    load_module(script_path=project_script)


def _get_new_python_path(project_dir: str) -> str:
    current_python_path = os.getenv('PYTHONPATH')
    if current_python_path is None or current_python_path == '':
        return project_dir
    return current_python_path + ':' + project_dir
