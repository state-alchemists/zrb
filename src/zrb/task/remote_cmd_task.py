from zrb.helper.accessories.color import colored
from zrb.helper.log import logger
from zrb.task.cmd_task import CmdTask

logger.debug(colored("Loading zrb.task.remote_cmd_task", attrs=["dark"]))

RemoteCmdTask = CmdTask
