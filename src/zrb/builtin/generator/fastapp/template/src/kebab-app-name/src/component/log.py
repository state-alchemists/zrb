from config import app_logging_level
import logging

# create logger
logger = logging.getLogger('src')
logger.setLevel(app_logging_level)

ch = logging.StreamHandler()
ch.setLevel(app_logging_level)

# create formatter
formatter = logging.Formatter(
    '%(levelname)s:\t%(message)s'
)

# add formatter to ch
ch.setFormatter(formatter)

# add ch to logger
logger.addHandler(ch)
