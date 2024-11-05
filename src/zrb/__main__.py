import sys

from .runner.cli import cli
from .util.cli.style import stylize_error
from .util.group import NodeNotFoundError


def serve_cli():
    try:
        cli.run(sys.argv[1:])
    except NodeNotFoundError as e:
        print(stylize_error(f"{e}"), file=sys.stderr)
