from typing import Optional
from .accessories.color import colored
from .log import logger
import os


def inject_default_env():
    if 'PYTHONUNBUFFERED' not in os.environ:
        logger.info(colored('Set PYTHONUNBUFFERED to 1', attrs=['dark']))
        os.environ['PYTHONUNBUFFERED'] = '1'

    zrb_home_dir = os.path.dirname(os.path.dirname(__file__))
    if 'ZRB_HOME_DIR' not in os.environ:
        logger.info(colored(
            f'Set ZRB_HOME_DIR to {zrb_home_dir}', attrs=['dark']
        ))
        os.environ['ZRB_HOME_DIR'] = zrb_home_dir

    logger.info(colored('Getting project directory', attrs=['dark']))
    current_dir = os.getcwd()
    zrb_project_dir = _get_project_dir(current_dir)
    if zrb_project_dir is None:
        zrb_project_dir = current_dir
    logger.info(colored(
        f'Set ZRB_PROJECT_DIR to {zrb_project_dir}', attrs=['dark']
    ))
    os.environ['ZRB_PROJECT_DIR'] = zrb_project_dir

    if 'ZRB_PROJECT_NAME' not in os.environ:
        zrb_project_name = os.path.basename(zrb_project_dir)
        logger.info(colored(
            f'Set ZRB_PROJECT_NAME to {zrb_project_name}', attrs=['dark']
        ))
        os.environ['ZRB_PROJECT_NAME'] = zrb_project_name


def _get_project_dir(project_dir: str) -> Optional[str]:
    project_script = os.path.join(project_dir, 'zrb_init.py')
    if os.path.isfile(project_script):
        return project_dir
    # zrb_init.py not found, look for it on the parent directory
    parent_project_dir = os.path.dirname(project_dir)
    if parent_project_dir == project_dir:
        return None
    return _get_project_dir(parent_project_dir)
