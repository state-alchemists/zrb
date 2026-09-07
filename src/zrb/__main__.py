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


def _load_or_warn(label: str, load: "Callable[[], Any]") -> None:
    """Load one init module/script, or report it precisely and move on.

    The error is never hidden — file, line, and exception type always print
    to stderr — but it is not fatal. A broken init source only ran up to its
    own failure point; whatever it already did (a `CFG` assignment, a task
    registration) before raising stays in effect, and whatever comes after
    that point in the same source is skipped. Startup continues with the
    next init source and then the CLI itself, since a user who can see the
    error and still run zrb can fix it and rerun, while a user who can't run
    zrb at all has a strictly worse time diagnosing the same error.
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
            _load_or_warn(
                f"init module {init_module}", lambda m=init_module: load_module(m)
            )
        zrb_init_path_list = get_init_path_list()
        for init_script in CFG.INIT_SCRIPTS:
            abs_init_script = os.path.abspath(os.path.expanduser(init_script))
            if abs_init_script not in zrb_init_path_list:
                CFG.LOGGER.info(f"Loading {abs_init_script}")
                _load_or_warn(
                    f"init script {abs_init_script}",
                    lambda p=abs_init_script: load_file(p, raise_on_error=True),
                )
        for zrb_init_path in zrb_init_path_list:
            CFG.LOGGER.info(f"Loading {zrb_init_path}")
            _load_or_warn(
                f"{zrb_init_path}",
                lambda p=zrb_init_path: load_file(p, raise_on_error=True),
            )
        cli.run(sys.argv[1:])
    except KeyboardInterrupt:
        # The exception is handled by the task runner
        print(stylize_warning("\nStopped"), file=sys.stderr)
        pass
    except RuntimeError as e:
        if f"{e}".lower() == "event loop is closed":
            sys.exit(1)
        _handle_uncaught(e)
    except NodeNotFoundError as e:
        print(stylize_error(f"{e}"), file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        _handle_uncaught(e)


def _handle_uncaught(error: Exception) -> None:
    """Report an exception that escaped task-level handling, or re-raise it.

    A permanently-failed task already logged its own clean summary (see
    `BaseTaskExecution.execute_action_with_retry`); letting it propagate here
    would just dump the same failure again as a raw traceback. Keep the full
    traceback available on demand via DEBUG, same as execution.py.

    The one-line summary carries no file or line, so it names the variable
    that unlocks the rest: under DEBUG this re-raises, and the traceback
    arrives with the `Task: <name> (<file>:<line>)` line attached.

    That variable is read off the field rather than hardcoded, because a
    white-labeled distribution sets its own `_ZRB_ENV_PREFIX` (see
    `docs/advanced-topics/white-labeling.md`) and reads `ACME_LOGGING_LEVEL`.
    """
    if CFG.LOGGER.isEnabledFor(logging.DEBUG):
        raise error
    debug_env_key = type(CFG).LOGGING_LEVEL.env_key(CFG.ENV_PREFIX)
    print(stylize_error(f"{type(error).__name__}: {error}"), file=sys.stderr)
    print(
        stylize_muted(f"For the full traceback: {debug_env_key}=DEBUG"),
        file=sys.stderr,
    )
    # Read off the exception rather than importing `CmdTaskError`: any error
    # that knows a meaningful process exit code can carry one, and `__main__`
    # has no reason to know which task types do.
    sys.exit(getattr(error, "return_code", 1) or 1)


if __name__ == "__main__":
    serve_cli()
