"""System-info (cwd + git) status for `BaseUI`.

Maintains the working-directory and git-branch indicators shown in the chat
UI, refreshed on a periodic loop. Split out of `ui.py` to keep that file
focused; composed into `BaseUI` as `self._system_info`, keeping the `BaseUI`
reference in `self._base_ui` for the state/methods it needs (`_cwd`,
`_git_info`, `invalidate_ui`).
"""

from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING

from zrb.config.config import CFG

if TYPE_CHECKING:
    from zrb.llm.ui.base.ui import BaseUI


async def _communicate_or_reap(proc) -> tuple[bytes, bytes]:
    """``proc.communicate()`` that kills + reaps the child on cancellation.

    The system-info loop is cancelled at session teardown, which can land while
    a ``git`` subprocess is mid-flight. An un-reaped child at loop close logs
    "Loop <...> that handles pid N is closed" when it exits, so unwind by
    terminating the child before propagating the cancellation.
    """
    try:
        return await proc.communicate()
    except asyncio.CancelledError:
        if proc.returncode is None:
            try:
                proc.terminate()
                await asyncio.wait_for(proc.wait(), timeout=1.0)
            except BaseException:
                try:
                    proc.kill()
                except Exception:
                    pass
        raise


class BaseUISystemInfo:
    """Track and periodically refresh cwd / git status for the UI."""

    def __init__(self, base_ui: "BaseUI") -> None:
        self._base_ui = base_ui

    async def _update_system_info(self):
        """Update CWD and Git info."""
        self._base_ui._cwd = self._get_cwd_display()
        branch, status = await self._get_git_info()
        if branch:
            self._base_ui._git_info = f"{branch}{status}"
        else:
            self._base_ui._git_info = "Not a git repo"
        self._base_ui.invalidate_ui()

    def _get_cwd_display(self) -> str:
        cwd = os.getcwd()
        home = os.path.expanduser("~")
        if cwd.startswith(home):
            return "~" + cwd[len(home) :]
        return cwd

    async def _get_git_info(self) -> tuple[str, str]:
        """Returns (branch_name, status_symbol)"""
        try:
            # Check branch
            proc = await asyncio.create_subprocess_exec(
                "git",
                "rev-parse",
                "--abbrev-ref",
                "HEAD",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await _communicate_or_reap(proc)
            if proc.returncode != 0:
                return "", ""
            branch = stdout.decode().strip()

            # Check status (dirty or clean)
            proc = await asyncio.create_subprocess_exec(
                "git",
                "status",
                "--porcelain",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await _communicate_or_reap(proc)
            is_dirty = bool(stdout.strip())

            return branch, "*" if is_dirty else ""
        except asyncio.CancelledError:
            raise
        except Exception:
            return "", ""

    async def _update_system_info_loop(self):
        """Periodically update CWD and Git info."""
        while True:
            try:
                # Through `self._base_ui` (not bare `self`):
                # `_update_system_info` is also a `BaseUI` delegator, and tests
                # patch it at that level.
                await self._base_ui._update_system_info()
            except asyncio.CancelledError:
                break
            except Exception as e:
                # Best-effort periodic refresh; keep the loop alive on transient
                # errors without spamming logs each tick.
                CFG.LOGGER.debug(f"System-info refresh failed: {e}")
            try:
                await asyncio.sleep(CFG.LLM_UI_LONG_STATUS_INTERVAL / 1000)
            except RuntimeError:
                # Event loop closed during shutdown
                break
