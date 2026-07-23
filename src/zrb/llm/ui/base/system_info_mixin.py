"""System-info (cwd + git) status for `BaseUI`.

Maintains the working-directory and git-branch indicators shown in the chat
UI, refreshed on a periodic loop. Split out of `ui.py` to keep that file
focused; the methods still run on the composed `BaseUI` instance (see the
host-class contract below), mirroring `CommandsMixin`.
"""

from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING

from zrb.config.config import CFG


class SystemInfoMixin:
    """Track and periodically refresh cwd / git status for the UI."""

    # Host-class contract: state and methods owned by `BaseUI`. Declared here
    # so type checkers can verify accesses; the block does not run at runtime.
    if TYPE_CHECKING:
        _cwd: str
        _git_info: str

        def invalidate_ui(self) -> None: ...

    async def _update_system_info(self):
        """Update CWD and Git info."""
        self._cwd = self._get_cwd_display()
        branch, status = await self._get_git_info()
        if branch:
            self._git_info = f"{branch}{status}"
        else:
            self._git_info = "Not a git repo"
        self.invalidate_ui()

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
            stdout, _ = await proc.communicate()
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
            stdout, _ = await proc.communicate()
            is_dirty = bool(stdout.strip())

            return branch, "*" if is_dirty else ""
        except Exception:
            return "", ""

    async def _update_system_info_loop(self):
        """Periodically update CWD and Git info."""
        while True:
            try:
                await self._update_system_info()
            except asyncio.CancelledError:
                break
            except Exception:
                # Best-effort periodic refresh; keep the loop alive on transient
                # errors without spamming logs each tick.
                pass
            try:
                await asyncio.sleep(CFG.LLM_UI_LONG_STATUS_INTERVAL / 1000)
            except RuntimeError:
                # Event loop closed during shutdown
                break
