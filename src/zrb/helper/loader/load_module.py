import importlib.util
import os
import re
import sys
from functools import lru_cache

from zrb.helper.accessories.color import colored
from zrb.helper.log import logger
from zrb.helper.typecheck import typechecked

pattern = re.compile("[^a-zA-Z0-9]")


@lru_cache
@typechecked
def load_module(script_path: str, add_to_system: bool = False):
    if not os.path.isfile(script_path):
        return
    script_dir_path = os.path.dirname(script_path)
    _append_dir_to_sys_path(script_dir_path)
    _append_dir_to_python_path(script_dir_path)
    _exec_script_as_module(script_path)


def _exec_script_as_module(script_path: str):
    module_name = pattern.sub("", script_path)
    logger.info(colored(f"Get module spec: {script_path}", attrs=["dark"]))
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    logger.info(colored(f"Create module: {script_path}", attrs=["dark"]))
    module = importlib.util.module_from_spec(spec)
    logger.info(colored(f"Exec module: {script_path}", attrs=["dark"]))
    spec.loader.exec_module(module)
    logger.info(colored(f"Module executed: {script_path}", attrs=["dark"]))


def _append_dir_to_sys_path(dir_path: str):
    sys.path.append(dir_path)
    logger.info(colored(f"Set sys.path to {sys.path}", attrs=["dark"]))


def _append_dir_to_python_path(dir_path: str):
    new_python_path = _get_new_python_path(dir_path)
    logger.info(colored(f"Set PYTHONPATH to {new_python_path}", attrs=["dark"]))
    os.environ["PYTHONPATH"] = new_python_path


def _get_new_python_path(dir_path: str) -> str:
    current_python_path = os.getenv("PYTHONPATH")
    if current_python_path is None or current_python_path == "":
        return dir_path
    return ":".join([current_python_path, dir_path])
