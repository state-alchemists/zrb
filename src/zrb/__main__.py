from .helper.cli.create_cli import create_cli
from .config.config import logging_level
from termcolor import colored
import logging

logging.basicConfig(
    level=logging_level,
    format=colored(
        '%(levelname)-8s %(asctime)s', attrs=['dark']
    ) + ' %(message)s'
)

logging.info('Creating CLI instance')
cli = create_cli()


if __name__ == '__main__':
    cli()
