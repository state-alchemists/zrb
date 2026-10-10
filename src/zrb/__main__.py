import logging
import os
import signal
import sys
import traceback
from collections.abc import Callable
from types import ModuleType
from typing import Any

from zrb.config.config import CFG
from zrb.config.init_path import get_init_path_list
from zrb.group.any_group import NodeNotFoundError
from zrb.group.task_diagnostics import (
    collect_declared_tasks,
    find_task_diagnostics,
    format_diagnostic,
    get_builtin_task_ids,
    reset_task_replacements,
)
from zrb.runner.cli import cli
from zrb.util.cli.style import stylize_error, stylize_muted, stylize_warning
from zrb.util.load import load_file_with_result, load_module_with_result


class FaintFormatter(logging.Formatter):

    def __init__(self, fmt=None, datefmt=None):
        default_fmt = "%(asctime)s %(levelname)s: %(message)s"
        default_datefmt = "%Y-%m-%d %H:%M:%S"
        super().__init__(fmt=fmt or default_fmt, datefmt=datefmt or default_datefmt)

    def format(self, record):
        log_msg = super().format(record)
        return stylize_muted(log_msg)


def _install_sigterm_handler() -> list[int]:
    """Treat SIGTERM like Ctrl+C, and return the list of stop signals received.

    The default SIGTERM action (`docker stop`, systemd, CI) would orphan
    running commands; the SIGINT handler cleans them up.
    """
    received: list[int] = []

    def handle_sigterm(signum: int, frame: Any) -> None:
        received.append(signum)
        sigint_handler = signal.getsignal(signal.SIGINT)
        if callable(sigint_handler):
            sigint_handler(signal.SIGINT, frame)
        else:
            raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, handle_sigterm)
    return received


def _load_or_warn(
    label: str,
    load: Callable[[], tuple[ModuleType | None, Exception | None]],
    loaded_sources: list[tuple[str, ModuleType]],
) -> bool:
    """Load one init module/script, or report the failure and move on.

    A partially loaded module is still appended to `loaded_sources`, since its
    side effects (task registrations) stay in effect. `sys.modules` cannot be
    used: every `zrb_init.py` registers under the same name.

    Returns:
        True when the source loaded cleanly.
    """
    module, error = load()
    if error is not None:
        _report_load_failure(label, error)
        if module is not None:
            loaded_sources.append((label, module))
        return False
    if module is not None:
        loaded_sources.append((label, module))
    return True


def _report_load_failure(label: str, error: Exception) -> None:
    """Print file, line, and exception type for an init source that failed."""
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
    for handler in CFG.LOGGER.handlers[:]:
        CFG.LOGGER.removeHandler(handler)
    handler = logging.StreamHandler()
    handler.setFormatter(FaintFormatter())
    CFG.LOGGER.addHandler(handler)
    stop_signals = _install_sigterm_handler()
    try:
        loaded_cleanly = True
        loaded_sources: list[tuple[str, ModuleType]] = []
        builtin_task_ids = get_builtin_task_ids()
        # `cli` outlives `serve_cli`.
        reset_task_replacements(cli)
        for init_module in CFG.INIT_MODULES:
            CFG.LOGGER.info(f"Loading {init_module}")
            loaded_cleanly &= _load_or_warn(
                f"init module {init_module}",
                lambda m=init_module: load_module_with_result(m),
                loaded_sources,
            )
        zrb_init_path_list = get_init_path_list()
        for init_script in CFG.INIT_SCRIPTS:
            abs_init_script = os.path.abspath(os.path.expanduser(init_script))
            if abs_init_script not in zrb_init_path_list:
                CFG.LOGGER.info(f"Loading {abs_init_script}")
                loaded_cleanly &= _load_or_warn(
                    f"init script {abs_init_script}",
                    lambda p=abs_init_script: load_file_with_result(p),
                    loaded_sources,
                )
        for zrb_init_path in zrb_init_path_list:
            CFG.LOGGER.info(f"Loading {zrb_init_path}")
            loaded_cleanly &= _load_or_warn(
                f"{zrb_init_path}",
                lambda p=zrb_init_path: load_file_with_result(p),
                loaded_sources,
            )
        # Checked after every source so one run reports every failure.
        if not loaded_cleanly and CFG.INIT_STRICT:
            print(
                stylize_error(
                    f"Aborting: an init source failed and {CFG.ENV_PREFIX}"
                    "_INIT_STRICT is on."
                ),
                file=sys.stderr,
            )
            sys.exit(1)
        _warn_mistyped_env_keys()
        _warn_task_diagnostics(loaded_sources, builtin_task_ids)
        cli.run(sys.argv[1:])
    except KeyboardInterrupt:
        print(stylize_warning("\nStopped"), file=sys.stderr)
        # 128 + signal number: the shell's convention for a signal exit.
        sys.exit(128 + (stop_signals[-1] if stop_signals else signal.SIGINT))
    except RuntimeError as e:
        if f"{e}".lower() == "event loop is closed":
            sys.exit(1)
        _handle_uncaught(e)
    except NodeNotFoundError as e:
        print(stylize_error(f"{e}"), file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        _handle_uncaught(e)


def _warn_task_diagnostics(
    loaded_sources: list[tuple[str, ModuleType]], builtin_task_ids: frozenset[int]
) -> None:
    """Warn about each declared task the CLI will not offer as expected."""
    declared = collect_declared_tasks(loaded_sources)
    for diagnostic in find_task_diagnostics(declared, cli, builtin_task_ids):
        print(
            stylize_warning(format_diagnostic(diagnostic)),
            file=sys.stderr,
        )


def _warn_mistyped_env_keys() -> None:
    """Warn about each set variable that looks like a setting but is not one.

    Runs after the init sources, which may set `ENV_PREFIX` or the variables.
    """
    for key, instead in CFG.get_retired_env_keys().items():
        if instead.startswith(f"{CFG.ENV_PREFIX}_"):
            message = f"{key} is no longer read and is ignored. Set {instead} instead."
        else:
            message = f"{key} is no longer read and is ignored: {instead}."
        print(stylize_warning(message), file=sys.stderr)
    for key, meant in CFG.get_mistyped_env_keys().items():
        print(
            stylize_warning(
                f"{key} is not a setting and is ignored. Did you mean {meant}?"
            ),
            file=sys.stderr,
        )


def _handle_uncaught(error: Exception) -> None:
    """Print a one-line summary of an escaped exception, or re-raise under DEBUG.

    A failed task already logged its own summary (see
    `BaseTaskExecution.execute_action_with_retry`). The debug variable name is
    derived from `ENV_PREFIX` to honour white-labeled distributions.
    """
    if CFG.LOGGER.isEnabledFor(logging.DEBUG):
        raise error
    debug_env_key = type(CFG).LOGGING_LEVEL.env_key(CFG.ENV_PREFIX)
    print(stylize_error(f"{type(error).__name__}: {error}"), file=sys.stderr)
    print(
        stylize_muted(f"For the full traceback: {debug_env_key}=DEBUG"),
        file=sys.stderr,
    )
    sys.exit(getattr(error, "return_code", 1) or 1)


if __name__ == "__main__":
    serve_cli()
