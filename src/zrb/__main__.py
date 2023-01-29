from .helper.cli.create_cli import create_cli
from .config.config import logging_level
from termcolor import colored
import logging

logging.basicConfig(
    level=logging_level,
    format=colored('%(levelname)s', attrs=['dark']) + ' %(message)s'
)
cli = create_cli()


if __name__ == '__main__':
    cli()
