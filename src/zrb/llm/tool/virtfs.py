"""Virtual Filesystem for context offloading.

This implements a context management system similar to Deep Agents, allowing
the LLM to offload large outputs to a virtual filesystem instead of keeping
them in memory. This prevents context window overflow.

Storage backends:
- In-memory (default, fastest)
- Local disk (persistent)
- Session-based (isolated per conversation)
"""

from __future__ import annotations

import json
import os
import shutil
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from zrb.config.config import CFG
from zrb.context.any_context import zrb_print

# Storage backend types
StorageBackend = Literal["memory", "disk", "session"]


class VirtualFilesystem:
    """
    Virtual filesystem for context offloading.

    Features:
    - Multiple storage backends (memory, disk, session)
    - Hierarchical paths (like a real filesystem)
    - Metadata support
    - Automatic cleanup
    - Session isolation

    Use cases:
    - Store large outputs from tools to avoid context overflow
    - Pass data between tool calls without using context
    - Cache intermediate results
    - Maintain scratchpad for complex operations
    """

    def __init__(
        self,
        backend: StorageBackend = "memory",
        root_dir: Path | str | None = None,
        max_size_mb: int = 100,
    ):
        self._backend = backend
        self._max_size_bytes = max_size_mb * 1024 * 1024
        self._current_size = 0

        # Storage
        self._memory_store: dict[str, dict[str, Any]] = {}

        # Thread lock for concurrent access
        self._lock = threading.RLock()

        # Set root directory for disk backend
        if root_dir:
            self._root_dir = Path(root_dir)
        else:
            self._root_dir = Path.home() / f".{CFG.ROOT_GROUP_NAME}" / "vfs"

        if backend == "disk":
            self._root_dir.mkdir(parents=True, exist_ok=True)

    def _get_session_dir(self, session: str | None) -> Path:
        """Get session-specific directory."""
        if session:
            safe_session = "".join(
                c if c.isalnum() or c in "-_" else "_" for c in session
            )
            return self._root_dir / "sessions" / safe_session
        return self._root_dir

    def _resolve_path(self, path: str, session: str | None = None) -> str:
        """Normalize path to prevent traversal attacks."""
        # Remove leading/trailing slashes, normalize
        path = path.strip("/").replace("\\", "/")

        # Prevent path traversal
        if ".." in path.split("/"):
            raise ValueError(f"Path traversal not allowed: {path}")

        # Add session prefix if using session backend
        if self._backend == "session" and session:
            safe_session = "".join(
                c if c.isalnum() or c in "-_" else "_" for c in session
            )
            path = f"sessions/{safe_session}/{path}"

        return path

    def _store_key(self, path: str, session: str | None = None) -> str:
        """Get the storage key for a path."""
        path = self._resolve_path(path, session)
        if session and self._backend != "memory":
            return f"{session}:{path}"
        return path

    def write(
        self,
        path: str,
        content: str | bytes | dict | list,
        session: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Write content to the virtual filesystem.

        Args:
            path: Virtual path (e.g., "scratch/output.txt", "cache/data.json")
            content: Content to write (string, bytes, or JSON-serializable dict/list)
            session: Session identifier for isolation
            metadata: Optional metadata to attach

        Returns:
            Info about the written file
        """
        with self._lock:
            key = self._store_key(path, session)

            # Serialize content
            if isinstance(content, (dict, list)):
                content_str = json.dumps(content, indent=2)
                content_bytes = content_str.encode("utf-8")
                content_type = "json"
            elif isinstance(content, bytes):
                content_bytes = content
                content_str = content.decode("utf-8", errors="replace")
                content_type = "binary"
            else:
                content_str = str(content)
                content_bytes = content_str.encode("utf-8")
                content_type = "text"

            # Check size limit
            new_size = len(content_bytes)

            # Store based on backend
            entry = {
                "path": path,
                "content": content_str if self._backend == "memory" else None,
                "content_bytes": content_bytes if self._backend == "memory" else None,
                "size": new_size,
                "type": content_type,
                "metadata": metadata or {},
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            }

            if self._backend == "memory":
                self._memory_store[key] = entry
                self._current_size += new_size

            elif self._backend in ("disk", "session"):
                # Write to disk
                if session and self._backend == "session":
                    file_path = self._get_session_dir(session) / path
                else:
                    file_path = self._root_dir / path

                file_path.parent.mkdir(parents=True, exist_ok=True)

                if isinstance(content, bytes):
                    file_path.write_bytes(content)
                else:
                    file_path.write_text(content_str, encoding="utf-8")

                # Write metadata
                meta_path = file_path.with_suffix(file_path.suffix + ".meta")
                meta_path.write_text(json.dumps(entry, indent=2), encoding="utf-8")

            zrb_print(f"  📝 VFS write: {path} ({new_size} bytes)", plain=True)

            return {
                "path": path,
                "size": new_size,
                "type": content_type,
                "written": True,
            }

    def read(
        self,
        path: str,
        session: str | None = None,
        as_type: Literal["text", "json", "bytes"] = "text",
    ) -> dict[str, Any]:
        """
        Read content from the virtual filesystem.

        Args:
            path: Virtual path
            session: Session identifier
            as_type: How to return the content (text, json, or bytes)

        Returns:
            Dict with content and metadata
        """
        with self._lock:
            key = self._store_key(path, session)

            # Try memory first
            if self._backend == "memory" and key in self._memory_store:
                entry = self._memory_store[key]
            elif self._backend in ("disk", "session"):
                # Try to read from disk
                if session and self._backend == "session":
                    file_path = self._get_session_dir(session) / path
                else:
                    file_path = self._root_dir / path

                if not file_path.exists():
                    return {
                        "path": path,
                        "found": False,
                        "error": f"File not found: {path}",
                    }

                # Read content
                if as_type == "bytes":
                    content = file_path.read_bytes()
                else:
                    content = file_path.read_text(encoding="utf-8")

                # Read metadata if exists
                meta_path = file_path.with_suffix(file_path.suffix + ".meta")
                if meta_path.exists():
                    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
                else:
                    metadata = {"path": path}

                entry = {
                    "path": path,
                    "content": content,
                    "size": file_path.stat().st_size,
                    "metadata": metadata,
                }
            else:
                return {
                    "path": path,
                    "found": False,
                    "error": f"File not found: {path}",
                }

            # Parse content based on as_type
            content = entry.get("content", "")

            if as_type == "json" and isinstance(content, str):
                try:
                    content = json.loads(content)
                except json.JSONDecodeError:
                    pass
            elif as_type == "bytes" and isinstance(content, str):
                content = content.encode("utf-8")

            return {
                "path": path,
                "found": True,
                "content": content,
                "size": entry.get(
                    "size", len(content) if isinstance(content, (str, bytes)) else 0
                ),
                "type": entry.get("type", "text"),
                "metadata": entry.get("metadata", {}),
            }

    def list(
        self,
        prefix: str = "",
        session: str | None = None,
    ) -> dict[str, Any]:
        """
        List files in the virtual filesystem.

        Args:
            prefix: Path prefix to filter (e.g., "scratch/", "cache/")
            session: Session identifier

        Returns:
            List of files with metadata
        """
        with self._lock:
            prefix = self._resolve_path(prefix, session)
            files = []

            if self._backend == "memory":
                for key, entry in self._memory_store.items():
                    if prefix and not key.startswith(prefix):
                        continue
                    files.append(
                        {
                            "path": entry["path"],
                            "size": entry["size"],
                            "type": entry.get("type", "text"),
                            "updated_at": entry.get("updated_at"),
                        }
                    )

            elif self._backend in ("disk", "session"):
                if session and self._backend == "session":
                    base_dir = self._get_session_dir(session)
                else:
                    base_dir = self._root_dir

                if prefix:
                    search_dir = base_dir / prefix
                else:
                    search_dir = base_dir

                if search_dir.exists():
                    for file_path in search_dir.rglob("*"):
                        if file_path.is_file() and not file_path.suffix.endswith(
                            ".meta"
                        ):
                            rel_path = str(file_path.relative_to(base_dir))
                            stat = file_path.stat()
                            files.append(
                                {
                                    "path": rel_path,
                                    "size": stat.st_size,
                                    "type": (
                                        "binary"
                                        if file_path.suffix in (".bin", ".pkl")
                                        else "text"
                                    ),
                                    "updated_at": datetime.fromtimestamp(
                                        stat.st_mtime
                                    ).isoformat(),
                                }
                            )

            return {
                "prefix": prefix,
                "count": len(files),
                "files": files,
            }

    def delete(
        self,
        path: str,
        session: str | None = None,
    ) -> dict[str, Any]:
        """
        Delete a file from the virtual filesystem.

        Args:
            path: Virtual path to delete
            session: Session identifier

        Returns:
            Deletion result
        """
        with self._lock:
            key = self._store_key(path, session)

            if self._backend == "memory":
                if key not in self._memory_store:
                    return {
                        "path": path,
                        "deleted": False,
                        "error": f"File not found: {path}",
                    }

                del self._memory_store[key]
                zrb_print(f"  🗑️ VFS delete: {path}", plain=True)
                return {"path": path, "deleted": True}

            elif self._backend in ("disk", "session"):
                if session and self._backend == "session":
                    file_path = self._get_session_dir(session) / path
                else:
                    file_path = self._root_dir / path

                if not file_path.exists():
                    return {
                        "path": path,
                        "deleted": False,
                        "error": f"File not found: {path}",
                    }

                file_path.unlink()

                # Also delete metadata file
                meta_path = file_path.with_suffix(file_path.suffix + ".meta")
                if meta_path.exists():
                    meta_path.unlink()

                zrb_print(f"  🗑️ VFS delete: {path}", plain=True)
                return {"path": path, "deleted": True}

            return {"path": path, "deleted": False, "error": "Unknown backend"}

    def clear(
        self,
        session: str | None = None,
        prefix: str = "",
    ) -> dict[str, Any]:
        """
        Clear files from the virtual filesystem.

        Args:
            session: Session identifier (clears only this session if backend is 'session')
            prefix: Only clear files matching this prefix

        Returns:
            Number of files cleared
        """
        with self._lock:
            count = 0

            if self._backend == "memory":
                keys_to_delete = []
                for key in self._memory_store:
                    if prefix and not key.startswith(prefix):
                        continue
                    keys_to_delete.append(key)

                for key in keys_to_delete:
                    del self._memory_store[key]
                    count += 1

            elif self._backend in ("disk", "session"):
                if session and self._backend == "session":
                    base_dir = self._get_session_dir(session)
                else:
                    base_dir = self._root_dir

                if base_dir.exists():
                    for file_path in base_dir.rglob("*"):
                        if file_path.is_file():
                            rel_path = str(file_path.relative_to(base_dir))
                            if prefix and not rel_path.startswith(prefix):
                                continue
                            file_path.unlink()
                            count += 1

            zrb_print(f"  🧹 VFS clear: {count} files", plain=True)
            return {"cleared": count}

    def get_stats(self, session: str | None = None) -> dict[str, Any]:
        """Get statistics about the virtual filesystem."""
        with self._lock:
            if self._backend == "memory":
                total_size = sum(e.get("size", 0) for e in self._memory_store.values())
                file_count = len(self._memory_store)
            else:
                if session and self._backend == "session":
                    base_dir = self._get_session_dir(session)
                else:
                    base_dir = self._root_dir

                total_size = 0
                file_count = 0

                if base_dir.exists():
                    for file_path in base_dir.rglob("*"):
                        if file_path.is_file() and not file_path.suffix.endswith(
                            ".meta"
                        ):
                            total_size += file_path.stat().st_size
                            file_count += 1

            return {
                "backend": self._backend,
                "file_count": file_count,
                "total_size_bytes": total_size,
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "max_size_mb": self._max_size_bytes // (1024 * 1024),
            }


# Global instance for memory backend (fastest)
_vfs_memory = VirtualFilesystem(backend="memory")

# Global instance for disk backend (persistent)
_vfs_disk = VirtualFilesystem(backend="disk")

# Session-specific VFS instances
_vfs_sessions: dict[str, VirtualFilesystem] = {}


def get_vfs(
    backend: StorageBackend = "memory", session: str | None = None
) -> VirtualFilesystem:
    """Get a VFS instance for the specified backend."""
    if backend == "memory":
        return _vfs_memory
    elif backend == "disk":
        return _vfs_disk
    elif backend == "session":
        if session not in _vfs_sessions:
            _vfs_sessions[session] = VirtualFilesystem(backend="session")
        return _vfs_sessions[session]
    else:
        raise ValueError(f"Unknown backend: {backend}")


# ============================================================================
# Tool Functions for LLM Integration
# ============================================================================


async def vfs_write(
    path: str,
    content: str,
    session: str | None = None,
    backend: StorageBackend = "memory",
) -> str:
    """
    Write content to the virtual filesystem.

    Use this to offload large outputs from tools and prevent context window overflow.
    The content is stored at a virtual path and can be read back later.

    **WHEN TO USE:**
    - Tool output is too large for context window
    - Intermediate results need to be passed between tools
    - Building a scratchpad for complex operations
    - Caching results for reuse

    **MANDATES:**
    - Use descriptive paths (e.g., "scratch/analysis_result.json")
    - Use ".json" extension for JSON content
    - Clean up temporary files when done with `vfs_delete`

    Args:
        path: Virtual path (e.g., "scratch/output.txt", "cache/data.json")
        content: Content to write (string, will be stored as-is)
        session: Session for isolation (uses current session if not provided)
        backend: Storage backend - "memory" (fastest), "disk" (persistent), "session" (isolated)

    Returns:
        Confirmation with path and size info
    """
    # Try to parse as JSON first
    try:
        content_obj = json.loads(content)
        result = get_vfs(backend, session).write(path, content_obj, session)
    except (json.JSONDecodeError, TypeError):
        result = get_vfs(backend, session).write(path, content, session)

    return json.dumps(result, indent=2)


async def vfs_read(
    path: str,
    session: str | None = None,
    backend: StorageBackend = "memory",
    as_json: bool = False,
) -> str:
    """
    Read content from the virtual filesystem.

    Use this to retrieve previously stored content.

    Args:
        path: Virtual path to read
        session: Session for isolation
        backend: Storage backend
        as_json: If True, parse content as JSON before returning

    Returns:
        The stored content (with metadata), or error if not found
    """
    as_type = "json" if as_json else "text"
    result = get_vfs(backend, session).read(path, session, as_type)

    if not result.get("found"):
        return json.dumps(result, indent=2)

    # Return content directly (not wrapped) for LLM consumption
    content = result.get("content")
    if isinstance(content, (dict, list)):
        return json.dumps(
            {"path": path, "content": content, "size": result.get("size")}, indent=2
        )
    else:
        return f"File: {path}\nSize: {result.get('size')} bytes\n\n{content}"


async def vfs_list(
    prefix: str = "",
    session: str | None = None,
    backend: StorageBackend = "memory",
) -> str:
    """
    List files in the virtual filesystem.

    Use this to see what files are stored, optionally filtered by path prefix.

    Args:
        prefix: Path prefix to filter (e.g., "scratch/", "cache/")
        session: Session for isolation
        backend: Storage backend

    Returns:
        List of files with sizes and types
    """
    result = get_vfs(backend, session).list(prefix, session)

    if not result["files"]:
        return f"No files found with prefix '{prefix}'"

    lines = [f"Virtual Filesytem - {result['count']} files in '{prefix}':", ""]
    for f in result["files"]:
        size_kb = f["size"] / 1024
        lines.append(f"  📄 {f['path']} ({size_kb:.1f} KB, {f.get('type', 'text')})")

    return "\n".join(lines)


async def vfs_delete(
    path: str,
    session: str | None = None,
    backend: StorageBackend = "memory",
) -> str:
    """
    Delete a file from the virtual filesystem.

    Args:
        path: Virtual path to delete
        session: Session for isolation
        backend: Storage backend

    Returns:
        Deletion confirmation
    """
    result = get_vfs(backend, session).delete(path, session)
    return json.dumps(result, indent=2)


async def vfs_clear(
    session: str | None = None,
    backend: StorageBackend = "memory",
    prefix: str = "",
) -> str:
    """
    Clear files from the virtual filesystem.

    Use this to clean up temporary files when done.

    Args:
        session: Session for isolation
        backend: Storage backend
        prefix: Only clear files matching this prefix

    Returns:
        Number of files cleared
    """
    result = get_vfs(backend, session).clear(session, prefix)
    return json.dumps(result, indent=2)


async def vfs_stats(
    session: str | None = None,
    backend: StorageBackend = "memory",
) -> str:
    """
    Get statistics about the virtual filesystem.

    Args:
        session: Session for isolation
        backend: Storage backend

    Returns:
        Statistics including file count and total size
    """
    result = get_vfs(backend, session).get_stats(session)
    return json.dumps(result, indent=2)


# Set function names for tool registration
vfs_write.__name__ = "VfsWrite"
vfs_read.__name__ = "VfsRead"
vfs_list.__name__ = "VfsList"
vfs_delete.__name__ = "VfsDelete"
vfs_clear.__name__ = "VfsClear"
vfs_stats.__name__ = "VfsStats"


def create_vfs_tools() -> list:
    """Create VFS tools for registration with LLM agent."""
    return [vfs_write, vfs_read, vfs_list, vfs_delete, vfs_clear, vfs_stats]
