from .runner.cli import cli
import sys


def serve_cli():
    cli.run(sys.argv[1:])
