from .cli_creator import create_cli
import logging

logging.basicConfig(level=logging.INFO)
cli = create_cli()


if __name__ == '__main__':
    cli()
