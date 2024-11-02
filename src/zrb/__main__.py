from .runner.cli import cli
from .runner.util import InvalidCommandError
from .util.cli.style import stylize_error
import sys


def serve_cli():
    try:
        cli.run(sys.argv[1:])
    except InvalidCommandError as e:
        print(stylize_error(f"{e}"), file=sys.stderr) 
