import importlib
from functools import lru_cache
from typing import Any

from zrb.helper.accessories.color import colored
from zrb.helper.log import logger
from zrb.helper.typecheck import typechecked

logger.debug(colored("Loading zrb.helper.loader.load_module", attrs=["dark"]))


@lru_cache
@typechecked
def load_module(module_name: str) -> Any:
    logger.info(colored(f"Importing module: {module_name}", attrs=["dark"]))
    module = importlib.import_module(module_name)
    logger.info(colored(f"Module imported: {module_name}", attrs=["dark"]))
    return module
