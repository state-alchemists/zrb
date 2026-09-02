import logging
import os
import sys
import traceback
from typing import Any, Callable

from zrb.config.config import CFG
from zrb.group.any_group import NodeNotFoundError
from zrb.runner.cli import cli
from zrb.util.cli.style import stylize_error, stylize_muted, stylize_warning
from zrb.util.init_path import get_init_path_list
from zrb.util.load import load_file, load_module


class FaintFormatter(logging.Formatter):

    def __init__(self, fmt=None, datefmt=None):
        default_fmt = "%(asctime)s %(levelname)s: %(message)s"
        default_datefmt = "%Y-%m-%d %H:%M:%S"
        super().__init__(fmt=fmt or default_fmt, datefmt=datefmt or default_datefmt)

    def format(self, record):
        log_msg = super().format(record)
        return stylize_muted(log_msg)


def _load_or_die(label: str, load: "Callable[[], Any]") -> None:
    """Load one init module/script, or report it precisely and exit non-zero.

    A partially applied config is worse than no config: the symptom shows up
    somewhere unrelated. So a failure here is fatal, and the message carries
    the file, the line and the exception type the user needs.
    """
    try:
        load()
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception as error:
        frame = traceback.extract_tb(error.__traceback__)[-1]
        print(
            stylize_error(
                f"Failed to load {label}\n"
                f"  {frame.filename}:{frame.lineno}\n"
                f"  {type(error).__name__}: {error}"
            ),
            file=sys.stderr,
        )
        sys.exit(1)


def serve_cli():
    CFG.LOGGER.setLevel(CFG.LOGGING_LEVEL)
    # Remove existing handlers to avoid duplicates/default formatting
    for handler in CFG.LOGGER.handlers[:]:
        CFG.LOGGER.removeHandler(handler)
    handler = logging.StreamHandler()
    handler.setFormatter(FaintFormatter())
    CFG.LOGGER.addHandler(handler)
    try:
        for init_module in CFG.INIT_MODULES:
            CFG.LOGGER.info(f"Loading {init_module}")
            _load_or_die(
                f"init module {init_module}", lambda m=init_module: load_module(m)
            )
        zrb_init_path_list = get_init_path_list()
        for init_script in CFG.INIT_SCRIPTS:
            abs_init_script = os.path.abspath(os.path.expanduser(init_script))
            if abs_init_script not in zrb_init_path_list:
                CFG.LOGGER.info(f"Loading {abs_init_script}")
                _load_or_die(
                    f"init script {abs_init_script}",
                    lambda p=abs_init_script: load_file(p, raise_on_error=True),
                )
        for zrb_init_path in zrb_init_path_list:
            CFG.LOGGER.info(f"Loading {zrb_init_path}")
            _load_or_die(
                f"{zrb_init_path}",
                lambda p=zrb_init_path: load_file(p, raise_on_error=True),
            )
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


if __name__ == "__main__":
    serve_cli()
