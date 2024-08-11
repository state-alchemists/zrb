from zrb.action.runner import Runner
from zrb.config.config import ENV_PREFIX
from zrb.helper.accessories.color import colored
from zrb.helper.log import logger

logger.debug(colored("Loading zrb.runner", attrs=["dark"]))
runner = Runner(env_prefix=ENV_PREFIX)
