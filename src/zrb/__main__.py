from .helper.cli import create_cli
from .helper.default_env import inject_default_env
from .helper.log import logger
from .helper.accessories.color import colored

inject_default_env()
logger.info(colored('Create CLI instance', attrs=['dark']))
cli = create_cli()

if __name__ == '__main__':
    cli()
