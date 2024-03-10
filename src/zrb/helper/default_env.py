import os
from functools import lru_cache

from zrb.helper.accessories.color import colored
from zrb.helper.log import logger
from zrb.helper.typecheck import typechecked
from zrb.helper.typing import Mapping, Optional

_PROJECT_DIR_MAP: Mapping[str, str] = {}


def inject_default_env():
    # Inject PYTHONUNBUFFERED
    if "PYTHONUNBUFFERED" not in os.environ:
        logger.info(colored("Set PYTHONUNBUFFERED to 1", attrs=["dark"]))
        os.environ["PYTHONUNBUFFERED"] = "1"
    # Inject ZRB_HOME_DIR
    if "ZRB_HOME_DIR" not in os.environ:
        default_home_dir = os.path.dirname(os.path.dirname(__file__))
        logger.info(colored(f"Set ZRB_HOME_DIR to {default_home_dir}", attrs=["dark"]))
        os.environ["ZRB_HOME_DIR"] = default_home_dir
    # Inject ZRB_PROJECT_DIR
    current_dir = os.getcwd()
    if current_dir not in _PROJECT_DIR_MAP:
        logger.info(colored("Getting project directory", attrs=["dark"]))
        zrb_project_dir = _get_project_dir(current_dir)
        if zrb_project_dir is None:
            zrb_project_dir = current_dir
        _PROJECT_DIR_MAP[current_dir] = zrb_project_dir
        logger.info(
            colored(f"Set ZRB_PROJECT_DIR to {zrb_project_dir}", attrs=["dark"])
        )
        os.environ["ZRB_PROJECT_DIR"] = zrb_project_dir
    # Inject ZRB_PROJECT_NAME
    if "ZRB_PROJECT_NAME" not in os.environ:
        zrb_project_name = os.path.basename(zrb_project_dir)
        logger.info(
            colored(f"Set ZRB_PROJECT_NAME to {zrb_project_name}", attrs=["dark"])
        )
        os.environ["ZRB_PROJECT_NAME"] = zrb_project_name


@lru_cache
@typechecked
def _get_project_dir(project_dir: str) -> Optional[str]:
    project_script = os.path.join(project_dir, "zrb_init.py")
    if os.path.isfile(project_script):
        return project_dir
    # zrb_init.py not found, look for it on the parent directory
    parent_project_dir = os.path.dirname(project_dir)
    if parent_project_dir == project_dir:
        return None
    return _get_project_dir(parent_project_dir)
