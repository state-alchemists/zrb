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
    message_count: int | None = None


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

    async def take_snapshot(
        self, label: str, message_count: int | None = None
    ) -> str | None:
        """Sync workdir → shadow dir and commit.  Returns commit SHA or None on error.

        Args:
            label: Human-readable label (typically the user message).
            message_count: Number of conversation messages at this point.  When
                provided it is embedded in the commit message so that restore can
                also rewind the conversation history to a consistent state.
        """
        try:
            self._ensure_initialized()
            await asyncio.to_thread(
                _sync_dirs, self._workdir, self._shadow_dir, True, True
            )
            commit_msg = _build_commit_message(label, message_count)
            return await asyncio.to_thread(self._commit, commit_msg)
        except Exception as e:
            logger.warning(f"Snapshot failed: {e}")
            return None

    def _commit(self, commit_msg: str) -> str | None:
        _git(self._shadow_dir, ["add", "-A"])
        result = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            cwd=self._shadow_dir,
            capture_output=True,
        )
        if result.returncode == 0:
            # Nothing new to commit — return current HEAD sha if any
            return _head_sha(self._shadow_dir)
        _git(self._shadow_dir, ["commit", "-m", commit_msg])
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
                    raw_label = parts[2]
                    label, message_count = _parse_commit_message(raw_label)
                    snapshots.append(
                        Snapshot(
                            sha=parts[0],
                            timestamp=parts[1],
                            label=label,
                            message_count=message_count,
                        )
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


_MC_TAG = "[mc:"  # message-count tag embedded in commit messages


def _build_commit_message(label: str, message_count: int | None) -> str:
    if message_count is None:
        return label
    return f"{label} {_MC_TAG}{message_count}]"


def _parse_commit_message(raw: str) -> tuple[str, int | None]:
    """Return (human_label, message_count).  message_count is None if not present."""
    import re

    m = re.search(r"\[mc:(\d+)\]$", raw)
    if m:
        return raw[: m.start()].rstrip(), int(m.group(1))
    return raw, None


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
            # Skip non-regular files (sockets, FIFOs, device files)
            if not os.path.isfile(src_path):
                continue
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

    # Remove empty directories (bottom-up).
    # Skip any path that is, or lives inside, a .git directory.
    for root, dirs, files in os.walk(dst, topdown=False):
        if root == dst:
            continue
        if exclude_git:
            rel = os.path.relpath(root, dst)
            if ".git" in rel.split(os.sep):
                continue
        try:
            if not os.listdir(root):
                os.rmdir(root)
        except OSError:
            pass
