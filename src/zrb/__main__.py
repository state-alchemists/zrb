import sys

from zrb.config import INIT_MODULES, INIT_SCRIPTS
from zrb.runner.cli import cli
from zrb.util.cli.style import stylize_error, stylize_warning
from zrb.util.group import NodeNotFoundError
from zrb.util.load import load_file, load_module


def serve_cli():
    try:
        for init_module in INIT_MODULES:
            load_module(init_module)
        for init_script in INIT_SCRIPTS:
            load_file(init_script, -1)
        cli.run(sys.argv[1:])
    except KeyboardInterrupt:
        print(stylize_warning("\nStopped"), file=sys.stderr)
        sys.exit(1)
    except RuntimeError as e:
        if f"{e}".lower() != "event loop is closed":
            raise e
        sys.exit(1)
    except NodeNotFoundError as e:
        print(stylize_error(f"{e}"), file=sys.stderr)
        sys.exit(1)
