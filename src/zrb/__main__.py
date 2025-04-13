import logging
import os
import sys

from zrb.config import INIT_MODULES, INIT_SCRIPTS, LOGGER, LOGGING_LEVEL
from zrb.runner.cli import cli
from zrb.util.cli.style import stylize_error, stylize_faint, stylize_warning
from zrb.util.group import NodeNotFoundError
from zrb.util.load import load_file, load_module


# Custom Formatter for faint styling
class FaintFormatter(logging.Formatter):

    def __init__(self, fmt=None, datefmt=None):
        default_fmt = "%(asctime)s %(levelname)s: %(message)s"
        default_datefmt = "%Y-%m-%d %H:%M:%S"
        super().__init__(fmt=fmt or default_fmt, datefmt=datefmt or default_datefmt)

    def format(self, record):
        log_msg = super().format(record)
        return stylize_faint(log_msg)


def serve_cli():
    LOGGER.setLevel(LOGGING_LEVEL)
    # Remove existing handlers to avoid duplicates/default formatting
    for handler in LOGGER.handlers[:]:
        LOGGER.removeHandler(handler)
    handler = logging.StreamHandler()
    handler.setFormatter(FaintFormatter())
    LOGGER.addHandler(handler)
    # --- End Logging Configuration ---
    try:
        # load init modules
        for init_module in INIT_MODULES:
            LOGGER.info(f"Loading {init_module}")
            load_module(init_module)
        zrb_init_path_list = _get_zrb_init_path_list()
        # load init scripts
        for init_script in INIT_SCRIPTS:
            abs_init_script = os.path.abspath(os.path.expanduser(init_script))
            if abs_init_script not in zrb_init_path_list:
                LOGGER.info(f"Loading {abs_init_script}")
                load_file(abs_init_script, -1)
        # load zrb init
        for zrb_init_path in zrb_init_path_list:
            LOGGER.info(f"Loading {zrb_init_path}")
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
        LOGGER.info(f"Finding {zrb_init_path}")
        if os.path.isfile(zrb_init_path):
            zrb_init_path_list.append(zrb_init_path)
    return zrb_init_path_list
