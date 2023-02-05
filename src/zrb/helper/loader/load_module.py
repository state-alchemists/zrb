from ..log import logger
import os
import re
import importlib.util
from ..accessories.color import colored

pattern = re.compile('[^a-zA-Z0-9]')


def load_module(script_path: str):
    if os.path.isfile(script_path):
        logger.info(colored(f'loading {script_path}', attrs=['dark']))
        module_name = pattern.sub('', script_path)
        spec = importlib.util.spec_from_file_location(module_name, script_path)
        # Create a module from the spec
        module = importlib.util.module_from_spec(spec)
        # Execute the module code
        spec.loader.exec_module(module)
