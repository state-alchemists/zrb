from ..config.config import logging_level
from .accessories.color import colored
import logging

# create logger
logger = logging.getLogger('zrb')
logger.setLevel(logging_level)

# create console handler and set level to debug
ch = logging.StreamHandler()
ch.setLevel(logging_level)

# create formatter
formatter = logging.Formatter(
    colored('%(levelname)-8s %(asctime)s', attrs=['dark']) + ' %(message)s'
)

# add formatter to ch
ch.setFormatter(formatter)

# add ch to logger
logger.addHandler(ch)
