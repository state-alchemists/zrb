import sys

from zrb.runner.cli import cli
from zrb.util.cli.style import stylize_error
from zrb.util.group import NodeNotFoundError


def serve_cli():
    try:
        cli.run(sys.argv[1:])
    except NodeNotFoundError as e:
        print(stylize_error(f"{e}"), file=sys.stderr)
