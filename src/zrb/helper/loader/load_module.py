from zrb.helper.typecheck import typechecked
from zrb.helper.log import logger
from zrb.helper.accessories.color import colored

import importlib.util
import os
import re

pattern = re.compile('[^a-zA-Z0-9]')


@typechecked
def load_module(script_path: str):
    if not os.path.isfile(script_path):
        return
    module_name = pattern.sub('', script_path)
    logger.info(colored(f'Get module spec: {script_path}', attrs=['dark']))
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    logger.info(colored(f'Create module: {script_path}', attrs=['dark']))
    module = importlib.util.module_from_spec(spec)
    logger.info(colored(f'Exec module: {script_path}', attrs=['dark']))
    spec.loader.exec_module(module)
    logger.info(colored(f'Module executed: {script_path}', attrs=['dark']))
