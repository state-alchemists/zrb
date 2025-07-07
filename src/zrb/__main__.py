import logging
import os
import sys

from zrb.config.config import CFG
from zrb.runner.cli import cli
from zrb.util.cli.style import stylize_error, stylize_faint, stylize_warning
from zrb.util.group import NodeNotFoundError
from zrb.util.init_path import get_init_path_list
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
    CFG.LOGGER.setLevel(CFG.LOGGING_LEVEL)
    # Remove existing handlers to avoid duplicates/default formatting
    for handler in CFG.LOGGER.handlers[:]:
        CFG.LOGGER.removeHandler(handler)
    handler = logging.StreamHandler()
    handler.setFormatter(FaintFormatter())
    CFG.LOGGER.addHandler(handler)
    # --- End Logging Configuration ---
    try:
        # load init modules
        for init_module in CFG.INIT_MODULES:
            CFG.LOGGER.info(f"Loading {init_module}")
            try:
                load_module(init_module)
            except BaseException as e:
                print(stylize_error(f"{e}"), file=sys.stderr)
        zrb_init_path_list = get_init_path_list()
        # load init scripts
        for init_script in CFG.INIT_SCRIPTS:
            abs_init_script = os.path.abspath(os.path.expanduser(init_script))
            if abs_init_script not in zrb_init_path_list:
                CFG.LOGGER.info(f"Loading {abs_init_script}")
                try:
                    load_file(abs_init_script, -1)
                except BaseException as e:
                    print(stylize_error(f"{e}"), file=sys.stderr)
        # load zrb init
        for zrb_init_path in zrb_init_path_list:
            CFG.LOGGER.info(f"Loading {zrb_init_path}")
            try:
                load_file(zrb_init_path)
            except BaseException as e:
                print(stylize_error(f"{e}"), file=sys.stderr)
        # run the CLI
        cli.run(sys.argv[1:])
    except KeyboardInterrupt:
        # The exception is handled by the task runner
        print(stylize_warning("\nStopped"), file=sys.stderr)
        pass
    except RuntimeError as e:
        if f"{e}".lower() != "event loop is closed":
            raise e
        sys.exit(1)
    except NodeNotFoundError as e:
        print(stylize_error(f"{e}"), file=sys.stderr)
        sys.exit(1)
