"""Cache-bearing IO helpers used by `InputCompleter`.

Loads shell history, Ollama model names, and a recursive file listing.
The two cached helpers take a small mutable cache dict so the caller
controls invalidation; this keeps `InputCompleter` ignorant of cache TTLs.
"""

from __future__ import annotations

import os
import subprocess
import time
from typing import Any

from zrb.config.config import CFG

_CACHE_TTL_SECONDS = 30


def load_cmd_history() -> list[str]:
    """Load deduplicated shell history (zsh + bash). Most-recent last."""
    history_files = [
        os.path.expanduser("~/.bash_history"),
        os.path.expanduser("~/.zsh_history"),
    ]
    unique_cmds: dict[str, None] = {}

    for hist_file in history_files:
        if not os.path.exists(hist_file):
            continue
        try:
            with open(hist_file, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    # zsh extended history: ": 1612345678:0;command"
                    if line.startswith(": ") and ";" in line:
                        parts = line.split(";", 1)
                        if len(parts) == 2:
                            line = parts[1]

                    if line:
                        # Bump to end so the most recent occurrence wins.
                        if line in unique_cmds:
                            del unique_cmds[line]
                        unique_cmds[line] = None
        except Exception:
            pass

    return list(unique_cmds.keys())


def load_ollama_models(cache: dict[str, Any]) -> list[str]:
    """Return Ollama models prefixed with `ollama:`. Caches in `cache` for 30s."""
    now = time.time()
    if (
        cache.get("models") is not None
        and now - cache.get("time", 0) < _CACHE_TTL_SECONDS
    ):
        return cache["models"]

    models: list[str] = []
    try:
        result = subprocess.run(
            ["ollama", "ls"],
            capture_output=True,
            text=True,
            timeout=CFG.LLM_MODEL_FETCH_TIMEOUT / 1000,
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")
            for line in lines[1:]:  # Skip header line
                parts = line.split()
                if parts:
                    models.append(f"ollama:{parts[0]}")
    except (subprocess.SubprocessError, FileNotFoundError, TimeoutError):
        pass

    cache["models"] = models
    cache["time"] = now
    return models


def walk_recursive_files(
    root: str,
    limit: int,
    cache: dict[str, Any],
) -> list[str]:
    """Walk `root` recursively, returning relative paths up to `limit`. 30s cache."""
    now = time.time()
    if (
        cache.get("files") is not None
        and now - cache.get("time", 0) < _CACHE_TTL_SECONDS
    ):
        return cache["files"]

    paths: list[str] = []
    cwd_is_hidden = os.path.basename(os.path.abspath(root)).startswith(".")

    try:
        for dirpath, dirnames, filenames in os.walk(root):
            if not cwd_is_hidden:
                dirnames[:] = [d for d in dirnames if not d.startswith(".")]
            dirnames[:] = [
                d
                for d in dirnames
                if d not in ("node_modules", "__pycache__", "venv", ".venv")
            ]

            rel_dir = os.path.relpath(dirpath, root)
            if rel_dir == ".":
                rel_dir = ""

            for d in dirnames:
                paths.append(os.path.join(rel_dir, d) + os.sep)
                if len(paths) >= limit:
                    cache["files"] = paths
                    cache["time"] = now
                    return paths

            for f in filenames:
                if not cwd_is_hidden and f.startswith("."):
                    continue
                paths.append(os.path.join(rel_dir, f))
                if len(paths) >= limit:
                    cache["files"] = paths
                    cache["time"] = now
                    return paths
    except Exception:
        pass

    cache["files"] = paths
    cache["time"] = now
    return paths
