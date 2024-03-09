from zrb.helper.accessories.color import colored
from zrb.helper.cli import create_cli
from zrb.helper.default_env import inject_default_env
from zrb.helper.log import logger

inject_default_env()
logger.info(colored("Create CLI instance", attrs=["dark"]))
cli = create_cli()

if __name__ == "__main__":
    cli()
