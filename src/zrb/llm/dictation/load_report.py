"""The lines a dictation session shows while a model loads.

A transcriber or the emotion detector says it is loading a model through the
*report* its `prepare` is handed. When it said so, a line of its own follows
once the load ends: a check mark when it is ready, a warning when it failed,
as the initial workspace snapshot's line does (ADR-0101). A model already
loaded says nothing, so nothing follows.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from zrb.util.cli.style import stylize_muted, stylize_warning

if TYPE_CHECKING:
    from zrb.llm.ui.any_ui import AnyUI

logger = logging.getLogger(__name__)

#: A `prepare` method: gets a model ready, saying so through the callable.
Prepare = Callable[[Callable[[str], None]], Awaitable[None]]


async def prepare_reported(
    name: str,
    prepare: Prepare,
    get_ui: Callable[[], "AnyUI | None"],
    get_failure: Callable[[], str] = lambda: "",
) -> None:
    """Run *prepare*, its lines going to the UI *get_ui* returns (else the
    log). When it announced a load, a line saying *name* is ready follows, or
    one saying it failed: because *prepare* raised, which is raised on, or
    because *get_failure* gives a reason once it returned."""
    is_announced = False

    def report(message: str) -> None:
        nonlocal is_announced
        is_announced = True
        write_line(get_ui(), f"🎤 {message}")

    try:
        await prepare(report)
    except Exception as exc:
        if is_announced:
            _write_failure(get_ui(), name, str(exc))
        raise
    if not is_announced:
        return
    failure = get_failure()
    if failure:
        _write_failure(get_ui(), name, failure)
    else:
        write_line(get_ui(), f"✅ {name} ready")


def write_line(ui: "AnyUI | None", line: str, is_warning: bool = False) -> None:
    """Show *line* on its own in *ui*'s output, else log it."""
    if ui is None:
        logger.warning(line)
        return
    style = stylize_warning if is_warning else stylize_muted
    ui.append_to_output(style(f"\n  {line}\n"))


def _write_failure(ui: "AnyUI | None", name: str, reason: str) -> None:
    write_line(ui, f"❗ {name} failed to load: {reason}", is_warning=True)
