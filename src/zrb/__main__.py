import os
import sys

from zrb.config import INIT_MODULES, INIT_SCRIPTS
from zrb.runner.cli import cli
from zrb.util.cli.style import stylize_error, stylize_warning
from zrb.util.group import NodeNotFoundError
from zrb.util.load import load_file, load_module


def serve_cli():
    try:
        # load init modules
        for init_module in INIT_MODULES:
            load_module(init_module)
        zrb_init_path_list = _get_zrb_init_path_list()
        # load init scripts
        for init_script in INIT_SCRIPTS:
            abs_init_script = os.path.abspath(os.path.expanduser(init_script))
            if abs_init_script not in zrb_init_path_list:
                load_file(abs_init_script, -1)
        # load zrb init
        for zrb_init_path in zrb_init_path_list:
            load_file(zrb_init_path)
        # run the CLI
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


def _get_zrb_init_path_list() -> list[str]:
    current_path = os.path.abspath(os.getcwd())
    dir_path_list = [current_path]
    while current_path != os.path.dirname(current_path):  # Stop at root
        current_path = os.path.dirname(current_path)
        dir_path_list.append(current_path)
    zrb_init_path_list = []
    for current_path in dir_path_list[::-1]:
        zrb_init_path = os.path.join(current_path, "zrb_init.py")
        if os.path.isfile(zrb_init_path):
            zrb_init_path_list.append(zrb_init_path)
    return zrb_init_path_list
