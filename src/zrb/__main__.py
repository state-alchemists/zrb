from zrb.helper.cli import create_cli
from zrb.helper.default_env import inject_default_env

inject_default_env()
cli = create_cli()

if __name__ == "__main__":
    cli()
