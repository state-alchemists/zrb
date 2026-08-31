"""Lossless overflow of oversized tool results to a queryable local store.

When ``LLM_ENABLE_TOOL_SPILL`` is on and a tool result's model-facing text
exceeds ``LLM_MAX_TOOL_RESULT_CHARS``, the wrapper (``agent/common.py``) spills
it here instead of passing it whole. The model sees a preview carrying a
``ReadToolResult`` handle; the full payload stays recoverable on demand.

Security mirrors pydantic-ai-harness's ``ToolOutputLimits``: the root is created
``0700``, and ``read`` resolves the target (following symlinks) and rejects
anything that escapes the root via symlink, ``..``, or an absolute path. Handle
segments are sanitized.

Leaf module: no ``pydantic_ai`` import at module load, so the hot tool-return
path stays cheap and nothing here drags the agent stack into a file write. See
ADR-0089.
"""

from __future__ import annotations

import json
import os
import re
import stat
import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from zrb.llm.agent_tool_result import has_multimodal
from zrb.llm.sandbox import check_read, check_write, get_effective_sandbox_policy


@runtime_checkable
class OverflowStore(Protocol):
    """Persist a payload under a key and read it back by handle."""

    def write(self, key: str, data: bytes) -> str: ...  # pragma: no cover
    def read(self, handle: str) -> bytes: ...  # pragma: no cover


_UNSAFE_SEGMENT = re.compile(r"[^A-Za-z0-9._-]+")


def _safe_segment(segment: str) -> str:
    """Make one path segment filesystem-safe without collapsing distinct keys."""
    cleaned = _UNSAFE_SEGMENT.sub("_", segment)
    return "_" if cleaned in ("", ".", "..") else cleaned


@dataclass
class LocalFileStore:
    """Dependency-free ``OverflowStore`` writing one file per spill.

    The handle equals the key: a relative path under ``base_dir``. The root is
    shared on purpose — a later run or agent can read a spill a previous run
    produced. Security comes from ``0700`` root permissions and the
    resolve-within-root check in ``read``, not from isolation.
    """

    base_dir: Path | None = None
    _root: Path = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._root = (
            self.base_dir
            if self.base_dir is not None
            else Path(tempfile.gettempdir()) / "zrb_spill"
        )

    @property
    def root(self) -> Path:
        """Directory that contains every payload handled by this store."""
        return self._root

    def _path(self, key: str) -> Path:
        segments = [_safe_segment(part) for part in key.split("/") if part]
        if not segments:
            segments = ["_"]
        return self._root.joinpath(*segments)

    def _ensure_root(self) -> None:
        try:
            self._root.mkdir(parents=True, mode=0o700)
        except FileExistsError:
            pass
        root_stat = self._root.lstat()
        if not stat.S_ISDIR(root_stat.st_mode) or self._root.is_symlink():
            raise PermissionError("Spill root must be a directory, not a symlink.")
        if hasattr(os, "getuid") and root_stat.st_uid != os.getuid():
            raise PermissionError("Spill root must be owned by the current user.")
        self._root.chmod(0o700)

    def write(self, key: str, data: bytes) -> str:
        self._ensure_root()
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return key

    def read(self, handle: str) -> bytes:
        self._ensure_root()
        target = self._path(handle).resolve()
        root = self._root.resolve()
        if not target.is_relative_to(root):
            raise PermissionError(f"Handle {handle!r} resolves outside the spill root.")
        return target.read_bytes()


#: Shared by the spill path and ``ReadToolResult``.
default_spill_store = LocalFileStore()


def _default_store_access_error(check: Any) -> str | None:
    """Return the active sandbox's objection to accessing the spill root."""
    policy = get_effective_sandbox_policy()
    if not policy.enabled:
        return None
    return check(str(default_spill_store.root), policy)


_PREVIEW_CHARS = 1_000
_MAX_READ_LINES = 1_000
_MAX_READ_CHARS = 50_000


def to_bytes(value: Any) -> bytes:
    """Serialize a tool return to the bytes that get spilled."""
    if isinstance(value, str):
        return value.encode("utf-8")
    if isinstance(value, memoryview):
        return value.tobytes()
    if isinstance(value, (bytes, bytearray)):
        return bytes(value)
    return json.dumps(value, default=str).encode("utf-8")


def _is_binary(value: Any) -> bool:
    return isinstance(value, (bytes, bytearray, memoryview))


def json_sketch(value: Any) -> str:
    """One-line shape hint for a structured value, or '' for anything else."""
    if isinstance(value, dict):
        keys = list(value)
        shown = ", ".join(f"{k!r}: {type(value[k]).__name__}" for k in keys[:10])
        more = "" if len(keys) <= 10 else f", ... ({len(keys)} keys)"
        return "{" + shown + more + "}"
    if isinstance(value, (list, tuple)) and not isinstance(
        value, (str, bytes, bytearray)
    ):
        elem = type(value[0]).__name__ if value else "empty"
        return f"[{len(value)} items of {elem}]"
    return ""


def _head_tail_preview(text: str, preview_chars: int) -> str:
    if len(text) <= preview_chars:
        return text
    head = preview_chars // 2
    tail = preview_chars - head
    omitted = len(text) - head - tail
    return f"{text[:head]}\n...[{omitted:,} chars omitted]...\n{text[-tail:]}"


def build_spill_preview(
    handle: str, value: Any, preview_chars: int = _PREVIEW_CHARS
) -> str:
    """Compose the model-visible stand-in: marker, shape sketch, head/tail preview."""
    if _is_binary(value):
        data = bytes(value)
        size_desc = f"{len(data):,} bytes (binary)"
        body = f"<{len(data):,} bytes of binary data>"
        sketch = ""
    else:
        text = value if isinstance(value, str) else json.dumps(value, default=str)
        size_desc = f"{len(text):,} chars"
        body = _head_tail_preview(text, preview_chars)
        sketch = json_sketch(value)
    header = (
        f"[Tool output too large ({size_desc}); stored to handle {handle!r}. "
        f"Read it with ReadToolResult(handle={handle!r}).]"
    )
    parts = [header]
    if sketch:
        parts.append(f"shape: {sketch}")
    parts.append(body)
    return "\n".join(parts)


def maybe_spill(value: Any, *, limit: int) -> tuple[Any, dict[str, Any]]:
    """Spill *value* when enabled and its model-facing text exceeds *limit*.

    Returns ``(value, {})`` unchanged when spill does not apply (disabled, under
    limit, multimodal, or the store write fails). On success returns
    ``(preview, {"overflow_handle": ..., "overflow_chars": ...})`` where the
    preview is the model-facing stand-in and the metadata is app-only.
    """
    # lazy: heavy transitive, and leaf modules must not import CFG at load time.
    from zrb.config.config import CFG

    if not CFG.LLM_ENABLE_TOOL_SPILL or limit <= 0:
        return value, {}

    if has_multimodal(value):
        return value, {}
    text = value if isinstance(value, str) else json.dumps(value, default=str)
    if len(text) <= limit:
        return value, {}
    if _default_store_access_error(check_write) is not None:
        return value, {}
    key = uuid.uuid4().hex
    try:
        handle = default_spill_store.write(key, to_bytes(value))
    except Exception:  # a store failure must not abort the tool result
        return value, {}
    return build_spill_preview(handle, value), {
        "overflow_handle": handle,
        "overflow_chars": len(text),
    }


def read_slice(
    store: OverflowStore,
    handle: str,
    offset: int,
    limit: int,
    from_end: bool,
    pattern: str | None,
) -> str:
    """Read a bounded slice of a spilled payload.

    ``pattern`` is a literal substring (not a regex) so a model-supplied value
    cannot hang the host with catastrophic backtracking.
    """
    if offset < 0 or limit < 1:
        return "[ReadToolResult: `offset` must be >= 0 and `limit` must be >= 1.]"
    limit = min(limit, _MAX_READ_LINES)
    try:
        data = store.read(handle)
    except OSError:
        # Return, not raise: a wrong handle (or a result no longer stored) must
        # not consume a tool retry. The store's error is intentionally not
        # echoed — it can carry a resolved filesystem path the model has no
        # need for.
        return (
            f"[No stored tool result for handle {handle!r}. Use the exact handle "
            "string from a '[Tool output too large ... stored to handle ...]' "
            "marker; if the result is no longer available, re-run the original tool.]"
        )
    lines = data.decode("utf-8", errors="replace").splitlines()
    if pattern is not None:
        lines = [line for line in lines if pattern in line]
    total = len(lines)
    if from_end:
        end = max(0, total - offset)
        window = lines[max(0, end - limit) : end]
    else:
        window = lines[offset : offset + limit]
    body = "\n".join(window)
    capped = ""
    if len(body) > _MAX_READ_CHARS:
        body = body[:_MAX_READ_CHARS]
        capped = ", output capped"
    header = f"[handle {handle!r}: {total:,} matching line(s); showing {len(window)}{capped}]"
    return f"{header}\n{body}" if body else header


def read_tool_result(
    handle: str,
    offset: int = 0,
    limit: int = 200,
    from_end: bool = False,
    pattern: str | None = None,
) -> str:
    """Read a slice of a spilled (overflowed) tool result.

    Args:
        handle: The handle from the "[Tool output too large ... stored to handle ...]"
            marker on a spilled tool result.
        offset: Number of matching lines to skip from the start (or the end when
            ``from_end``). Must be >= 0.
        limit: Maximum number of lines to return (>= 1; clamped to a built-in cap).
        from_end: Count ``offset``/``limit`` from the end of the result.
        pattern: Optional literal substring; only lines containing it are returned.
    """
    if _default_store_access_error(check_read) is not None:
        return "[Blocked by sandbox policy: the spilled result is not readable.]"
    return read_slice(default_spill_store, handle, offset, limit, from_end, pattern)


read_tool_result.__name__ = "ReadToolResult"
