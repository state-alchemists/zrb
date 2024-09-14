import logging

from zrb.config.config import LOGGING_LEVEL
from zrb.helper.accessories.untyped_color import untyped_colored as colored

# create logger
logger = logging.getLogger("zrb")
logger.setLevel(LOGGING_LEVEL)

# create console handler and set level to debug
ch = logging.StreamHandler()
ch.setLevel(LOGGING_LEVEL)

# create formatter
formatter = logging.Formatter(
    colored("%(levelname)-6s %(asctime)s", attrs=["dark"]) + " %(message)s"
)

# add formatter to ch
ch.setFormatter(formatter)

# add ch to logger
logger.addHandler(ch)
