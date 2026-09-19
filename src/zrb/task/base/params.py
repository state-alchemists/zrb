"""Keyword-parameter groups task constructors forward, as `TypedDict`s.

A task subclass declares only the keywords it adds and takes the rest as
`**kwargs: Unpack[BaseTaskParams]`, so a parameter shared with its parent is
spelled out in exactly one place. The call site is unaffected —
`CmdTask(name="build", cmd="make", retries=0)` binds as it reads, pyright
completes every forwarded name and rejects `retrie=0` — and adding a keyword
to `BaseTask` reaches every subclass by editing one `TypedDict` here.

The hierarchy mirrors what the classes accept, which is not one flat set:

- `CheckTaskParams` — what a readiness check takes. `HttpCheck` and `TcpCheck`
  exclude the retry/readiness cluster: a check polls on its own `interval` and
  is itself what a task waits on, so accepting a `readiness_check` would nest
  a check inside itself.
- `BaseTaskParams` — the above plus that cluster, i.e. `BaseTask`'s keywords
  less `action`, which every subclass supplies itself.
- `ActionTaskParams` — adds `action` back, for a subclass that forwards it.
- `CmdTaskParams` / `BaseTriggerParams` — each adds its own class's keywords,
  for the two classes that are themselves forwarded to (`RsyncTask` from
  `CmdTask`, `Scheduler` from `BaseTrigger`).

Prose for each parameter lives in the constructor docstring of the class that
owns it: `BaseTask.__init__` documents this whole set, and a forwarding
subclass names that class instead of restating it — enforced by
`test_a_forwarding_constructor_names_the_set_it_forwards`.
"""

from __future__ import annotations

from typing import Any, Callable, Sequence, TypedDict

from zrb.attr.tpl import Tpl
from zrb.attr.type import BoolAttr, IntAttr, StrAttr
from zrb.callback.any_callback import AnyCallback
from zrb.context.any_context import AnyContext
from zrb.context.print_fn import PrintFn
from zrb.env.any_env import AnyEnv
from zrb.input.any_input import AnyInput
from zrb.task.any_task import AnyTask


class CheckTaskParams(TypedDict, total=False):
    """`BaseTask` keywords a readiness check accepts.

    Excludes the retry/readiness cluster — see this module's docstring.
    """

    color: int | None
    icon: str | None
    description: str | None
    cli_only: bool
    input: Sequence[AnyInput | None] | AnyInput | None
    env: Sequence[AnyEnv | None] | AnyEnv | None
    execute_condition: BoolAttr
    upstream: Sequence[AnyTask] | AnyTask | None
    fallback: Sequence[AnyTask] | AnyTask | None
    successor: Sequence[AnyTask] | AnyTask | None
    print_fn: PrintFn | None


class BaseTaskParams(CheckTaskParams, total=False):
    """Every `BaseTask` keyword except `action`, which subclasses supply."""

    retries: int
    retry_period: float
    retry_if: Callable[[BaseException], bool] | None
    readiness_check: Sequence[AnyTask] | AnyTask | None
    readiness_check_delay: float | None
    readiness_check_period: float | None
    readiness_failure_threshold: int | None
    readiness_timeout: int | None
    monitor_readiness: bool


class ActionTaskParams(BaseTaskParams, total=False):
    """`BaseTaskParams` plus `action`, for a subclass that forwards it."""

    action: str | Tpl | Callable[[AnyContext], Any] | None


class CmdTaskParams(BaseTaskParams, total=False):
    """`CmdTask`'s own keywords, for the subclasses that copy them.

    `cmd` and `warn_unrecommended_command` are excluded: `RsyncTask` generates
    its command from the source/destination paths, so neither is meaningful
    there, and it is the only class copying this set.
    """

    shell: StrAttr | None
    shell_flag: StrAttr | None
    remote_host: StrAttr | None
    remote_port: IntAttr | None
    remote_user: StrAttr | None
    remote_password: StrAttr | None
    remote_ssh_key: StrAttr | None
    cwd: str | None
    plain_print: bool
    max_output_line: int
    max_error_line: int
    execution_timeout: int
    is_interactive: bool


class BaseTriggerParams(ActionTaskParams, total=False):
    """`BaseTrigger`'s own keywords, for `Scheduler`."""

    queue_name: str | None
    callback: list[AnyCallback] | AnyCallback | None


# What `BaseTask` accepts that a readiness check deliberately does not.
_CHECK_EXCLUDED = frozenset(BaseTaskParams.__optional_keys__) - frozenset(
    CheckTaskParams.__optional_keys__
)

# What `CmdTask` accepts that `RsyncTask` does not: it builds its own command
# by overriding `_get_cmd_script`, so `cmd` would be stored and then ignored.
_RSYNC_EXCLUDED = frozenset({"cmd", "warn_unrecommended_command"})


def reject_excluded_params(
    class_name: str, kwargs: dict[str, Any], excluded: frozenset[str], reason: str
) -> None:
    """Enforce a narrowed parameter set for callers pyright never saw.

    A subclass that accepts fewer keywords than its parent says so through a
    narrower `TypedDict`, which the type checker enforces. A hand-written
    `zrb_init.py` is not type-checked, so without this guard `**kwargs`
    forwards an excluded keyword straight through to the parent, where it is
    accepted and then ignored.
    """
    passed = sorted(excluded & kwargs.keys())
    if passed:
        raise TypeError(f"{class_name} does not accept {', '.join(passed)}: {reason}")


def reject_non_check_params(class_name: str, kwargs: dict[str, Any]) -> None:
    """`reject_excluded_params` for `HttpCheck` / `TcpCheck`."""
    reject_excluded_params(
        class_name,
        kwargs,
        _CHECK_EXCLUDED,
        "a readiness check polls on its own `interval` and is itself what a "
        "task waits on, so retry and readiness settings would nest a check "
        "inside itself. Set them on the task being checked instead.",
    )


def reject_non_rsync_params(class_name: str, kwargs: dict[str, Any]) -> None:
    """`reject_excluded_params` for `RsyncTask`."""
    reject_excluded_params(
        class_name,
        kwargs,
        _RSYNC_EXCLUDED,
        "its command is generated from the source and destination paths, so a "
        "command you supply here would be stored and never run.",
    )
