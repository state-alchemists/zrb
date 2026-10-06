"""Periodically refreshed cwd and git-branch indicators for `BaseUI`."""

from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING

from zrb.config.config import CFG

if TYPE_CHECKING:
    from zrb.llm.ui.base.ui import BaseUI


async def communicate_or_reap(proc) -> tuple[bytes, bytes]:
    """``proc.communicate()`` that kills + reaps the child on cancellation.

    An un-reaped child at loop close logs "Loop <...> that handles pid N is
    closed" when it exits.
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
                except OSError:
                    # Already gone, or the kill was refused.
                    pass
        raise


class BaseUISystemInfo:
    """Track and periodically refresh cwd / git status for the UI."""

    def __init__(self, base_ui: "BaseUI") -> None:
        self._base_ui = base_ui

    async def update_system_info(self):
        """Update CWD and Git info."""
        self._base_ui.cwd = self.get_cwd_display()
        branch, status = await self.get_git_info()
        if branch:
            self._base_ui.git_info = f"{branch}{status}"
        else:
            self._base_ui.git_info = "Not a git repo"
        self._base_ui.invalidate_ui()

    def get_cwd_display(self) -> str:
        cwd = os.getcwd()
        home = os.path.expanduser("~")
        if cwd == home or cwd.startswith(home + os.sep):
            return "~" + cwd[len(home) :]
        return cwd

    async def get_git_info(self) -> tuple[str, str]:
        """Returns (branch_name, status_symbol)"""
        try:
            proc = await asyncio.create_subprocess_exec(
                "git",
                "rev-parse",
                "--abbrev-ref",
                "HEAD",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await communicate_or_reap(proc)
            if proc.returncode != 0:
                return "", ""
            branch = stdout.decode().strip()

            proc = await asyncio.create_subprocess_exec(
                "git",
                "status",
                "--porcelain",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await communicate_or_reap(proc)
            is_dirty = bool(stdout.strip())

            return branch, "*" if is_dirty else ""
        except asyncio.CancelledError:
            raise
        except Exception:
            return "", ""

    async def update_system_info_loop(self):
        """Periodically update CWD and Git info."""
        while True:
            try:
                # Via the owner: tests patch `BaseUI.update_system_info`.
                await self._base_ui.update_system_info()
            except asyncio.CancelledError:
                break
            except Exception as e:
                CFG.LOGGER.debug(f"System-info refresh failed: {e}")
            try:
                await asyncio.sleep(CFG.LLM_UI_LONG_STATUS_INTERVAL / 1000)
            except RuntimeError:
                # Event loop closed during shutdown
                break
