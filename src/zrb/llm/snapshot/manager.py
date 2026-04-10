"""Shadow-git snapshot manager for LLM rewind functionality.

Each snapshot is a git commit in an isolated shadow repository located at
``<snapshot_dir>/<safe_session_name>/``.  The shadow repo is completely
separate from the project's own git history.

Snapshot flow:
    1. Copy workdir → shadow dir (excluding .git trees)
    2. ``git add -A && git commit`` in shadow dir

Restore flow:
    1. ``git reset --hard <sha>`` in shadow dir
    2. Copy shadow dir → workdir (with deletion of files absent from snapshot)
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import subprocess
from typing import NamedTuple

logger = logging.getLogger(__name__)


class Snapshot(NamedTuple):
    sha: str
    timestamp: str
    label: str


class SnapshotManager:
    """Manages filesystem snapshots using a shadow git repository."""

    def __init__(self, snapshot_dir: str, session_name: str, workdir: str):
        self._workdir = os.path.abspath(workdir)
        self._shadow_dir = os.path.join(snapshot_dir, _safe_name(session_name))
        self._initialized = False

    def _ensure_initialized(self):
        if self._initialized:
            return
        os.makedirs(self._shadow_dir, exist_ok=True)
        if not os.path.isdir(os.path.join(self._shadow_dir, ".git")):
            _git(self._shadow_dir, ["init"])
            _git(self._shadow_dir, ["config", "user.email", "zrb-snapshot@local"])
            _git(self._shadow_dir, ["config", "user.name", "zrb-snapshot"])
        self._initialized = True

    async def take_snapshot(self, label: str) -> str | None:
        """Sync workdir → shadow dir and commit.  Returns commit SHA or None on error."""
        try:
            self._ensure_initialized()
            await asyncio.to_thread(
                _sync_dirs, self._workdir, self._shadow_dir, True, True
            )
            return await asyncio.to_thread(self._commit, label)
        except Exception as e:
            logger.warning(f"Snapshot failed: {e}")
            return None

    def _commit(self, label: str) -> str | None:
        _git(self._shadow_dir, ["add", "-A"])
        result = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            cwd=self._shadow_dir,
            capture_output=True,
        )
        if result.returncode == 0:
            # Nothing new to commit — return current HEAD sha if any
            return _head_sha(self._shadow_dir)
        _git(self._shadow_dir, ["commit", "-m", label])
        return _head_sha(self._shadow_dir)

    def list_snapshots(self) -> list[Snapshot]:
        """Return snapshots in reverse chronological order (newest first)."""
        try:
            self._ensure_initialized()
            result = subprocess.run(
                ["git", "log", "--format=%H|%ai|%s", "--no-merges"],
                cwd=self._shadow_dir,
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                return []
            snapshots: list[Snapshot] = []
            for line in result.stdout.strip().splitlines():
                if not line.strip():
                    continue
                parts = line.split("|", 2)
                if len(parts) == 3:
                    snapshots.append(
                        Snapshot(sha=parts[0], timestamp=parts[1], label=parts[2])
                    )
            return snapshots
        except Exception as e:
            logger.warning(f"list_snapshots failed: {e}")
            return []

    async def restore_snapshot(self, sha: str) -> bool:
        """Restore workdir to the state captured at the given snapshot SHA."""
        try:
            self._ensure_initialized()
            await asyncio.to_thread(_git, self._shadow_dir, ["reset", "--hard", sha])
            await asyncio.to_thread(
                _sync_dirs, self._shadow_dir, self._workdir, True, True
            )
            return True
        except Exception as e:
            logger.warning(f"restore_snapshot failed: {e}")
            return False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _safe_name(name: str) -> str:
    """Convert an arbitrary session name to a filesystem-safe directory name."""
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in name)


def _head_sha(git_dir: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=git_dir,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except Exception:
        return None


def _git(cwd: str, args: list[str]):
    subprocess.run(["git"] + args, cwd=cwd, check=True, capture_output=True)


def _sync_dirs(
    src: str, dst: str, exclude_git: bool = True, delete: bool = False
) -> None:
    """Recursively copy *src* into *dst*, optionally deleting stale dst files.

    Args:
        src: Source directory path.
        dst: Destination directory path.
        exclude_git: When True, ``.git`` subtrees are skipped in both directions.
        delete: When True, files present in *dst* but absent from *src* are removed.
    """
    os.makedirs(dst, exist_ok=True)
    src_rel_paths: set[str] = set()

    # Copy src → dst
    for root, dirs, files in os.walk(src):
        if exclude_git and ".git" in dirs:
            dirs.remove(".git")

        rel_root = os.path.relpath(root, src)

        for fname in files:
            src_path = os.path.join(root, fname)
            rel_path = fname if rel_root == "." else os.path.join(rel_root, fname)
            dst_path = os.path.join(dst, rel_path)
            src_rel_paths.add(rel_path)
            os.makedirs(os.path.dirname(dst_path), exist_ok=True)
            shutil.copy2(src_path, dst_path)

    if not delete:
        return

    # Collect dst files (excluding .git)
    dst_rel_paths: set[str] = set()
    for root, dirs, files in os.walk(dst):
        if exclude_git and ".git" in dirs:
            dirs.remove(".git")

        rel_root = os.path.relpath(root, dst)
        for fname in files:
            rel_path = fname if rel_root == "." else os.path.join(rel_root, fname)
            dst_rel_paths.add(rel_path)

    # Remove stale files
    for rel_path in dst_rel_paths - src_rel_paths:
        try:
            os.remove(os.path.join(dst, rel_path))
        except OSError:
            pass

    # Remove empty directories (bottom-up, skip .git)
    for root, dirs, files in os.walk(dst, topdown=False):
        if exclude_git and os.path.basename(root) == ".git":
            continue
        if root == dst:
            continue
        try:
            if not os.listdir(root):
                os.rmdir(root)
        except OSError:
            pass
