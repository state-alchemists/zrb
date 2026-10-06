"""Keyword-parameter groups task constructors forward, as `TypedDict`s.

A subclass declares only the keywords it adds and takes the rest as
`**kwargs: Unpack[BaseTaskParams]`. Parameters are documented in
`BaseTask.__init__`.

- `CheckTaskParams`: `HttpCheck`/`TcpCheck`, without the retry/readiness keys.
- `BaseTaskParams`: `BaseTask`'s keywords except `action`.
- `ActionTaskParams`: adds `action`.
- `CmdTaskParams` / `BaseTriggerParams`: forwarded by `RsyncTask` / `Scheduler`.
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
    """`BaseTask` keywords a readiness check accepts."""

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
    readiness_timeout: float | None
    monitor_readiness: bool


class ActionTaskParams(BaseTaskParams, total=False):
    """`BaseTaskParams` plus `action`, for a subclass that forwards it."""

    action: str | Tpl | Callable[[AnyContext], Any] | None


class CmdTaskParams(BaseTaskParams, total=False):
    """`CmdTask`'s own keywords except `cmd`/`warn_unrecommended_command`."""

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


_CHECK_EXCLUDED = frozenset(BaseTaskParams.__optional_keys__) - frozenset(
    CheckTaskParams.__optional_keys__
)

_RSYNC_EXCLUDED = frozenset({"cmd", "warn_unrecommended_command"})


def reject_excluded_params(
    class_name: str, kwargs: dict[str, Any], excluded: frozenset[str], reason: str
) -> None:
    """Raise `TypeError` for excluded keywords; `zrb_init.py` is not type-checked."""
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
