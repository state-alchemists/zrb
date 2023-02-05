from .helper.cli import create_cli
from .helper.log import logger
from .helper.accessories.color import colored

logger.info(colored('Creating CLI instance', attrs=['dark']))
cli = create_cli()

if __name__ == '__main__':
    cli()
