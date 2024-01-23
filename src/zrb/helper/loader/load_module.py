import logging
import os
import re
from functools import lru_cache

from zrb.config.config import logging_level
from zrb.helper.accessories.color import colored
from zrb.helper.log import logger
from zrb.helper.typecheck import typechecked

pattern = re.compile("[^a-zA-Z0-9]")


@lru_cache
@typechecked
def load_module(script_path: str):
    if not os.path.isfile(script_path):
        return
    import importlib.util

    module_name = pattern.sub("", script_path)
    if logging_level <= logging.INFO:
        logger.info(colored(f"Get module spec: {script_path}", attrs=["dark"]))
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    if logging_level <= logging.INFO:
        logger.info(colored(f"Create module: {script_path}", attrs=["dark"]))
    module = importlib.util.module_from_spec(spec)
    if logging_level <= logging.INFO:
        logger.info(colored(f"Exec module: {script_path}", attrs=["dark"]))
    spec.loader.exec_module(module)
    if logging_level <= logging.INFO:
        logger.info(colored(f"Module executed: {script_path}", attrs=["dark"]))
