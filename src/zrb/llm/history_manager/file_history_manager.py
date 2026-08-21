import json
import os
import re
import warnings
from collections import OrderedDict
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pydantic_ai import ModelMessage

from zrb.config.config import CFG
from zrb.context.any_context import zrb_print
from zrb.llm.history_manager.any_history_manager import AnyHistoryManager
from zrb.llm.util.subagent_session_naming import (
    SUBAGENT_HISTORY_SUBDIR,
    parse_delegated_session,
    subagent_history_directories,
)
from zrb.util.match import fuzzy_match
from zrb.util.string.conversion import to_string

# Pattern to match timestamp suffix like -2024-03-18-10-30-00 or -2024-03-18-10-30
_TIMESTAMP_PATTERN = re.compile(r"-\d{4}-\d{2}-\d{2}-\d{2}-\d{2}(?:-\d{2})?$")

# Pattern to match a timestamped backup filename for a given base name.
# Captures: "<base>-YYYY-MM-DD-HH-MM[-SS][-N].json".
_BACKUP_FILENAME_PATTERN = re.compile(
    r"^(?P<base>.+)-\d{4}-\d{2}-\d{2}-\d{2}-\d{2}(?:-\d{2})?(?:-\d+)?\.json$"
)

# In-RAM cache bound: the most-recently-used conversations kept in memory.
# Evicted entries reload losslessly from disk on next access, so the bound
# only trades a re-read for memory in long sessions that touch many
# conversations.
_MAX_CACHED_CONVERSATIONS = 8


def _safe_segment(name: str) -> str:
    """A filesystem-safe single path segment for *name* (also used for the
    per-agent-type subdirectory, which is the agent name)."""
    safe = "".join(c for c in name if c.isalnum() or c in (" ", ".", "_", "-")).strip()
    return safe or "default"


class FileHistoryManager(AnyHistoryManager):
    def __init__(self, history_dir: str):
        self._history_dir = os.path.expanduser(history_dir)
        # LRU-ordered: most recently used entries at the end (see _evict_lru).
        self._cache: "OrderedDict[str, list[ModelMessage]]" = OrderedDict()
        # mtime of the on-disk file at the time the cache entry was last synced
        # with disk. Used to invalidate the cache when the file changes out-of-band
        # (a second manager instance, an external edit, a name that collides on one
        # file). `None` means "no file on disk at sync time".
        self._cache_mtime: dict[str, float | None] = {}
        # Conversations updated in memory but not yet persisted by save().
        # Dirty entries are never evicted — dropping them would lose data
        # that exists only in RAM.
        self._dirty: set[str] = set()
        if not os.path.exists(self._history_dir):
            os.makedirs(self._history_dir, exist_ok=True)

    def is_dirty(self, conversation_name: str) -> bool:
        """Whether *conversation_name* has in-memory updates not yet persisted."""
        return conversation_name in self._dirty

    def cache_sync_mtime(self, conversation_name: str) -> "float | None":
        """The on-disk mtime this conversation's cache entry was last synced
        to, or None if it has never been synced (or had no file at sync
        time)."""
        return self._cache_mtime.get(conversation_name)

    def load(self, conversation_name: str) -> "list[ModelMessage]":
        # lazy: heavy third-party
        from pydantic import ValidationError
        from pydantic_ai.messages import ModelMessagesTypeAdapter

        file_path, current_mtime = self._resolve_read_path(conversation_name)

        # Serve from cache only while the on-disk file hasn't changed since we
        # last synced. A differing mtime (incl. the file appearing/disappearing)
        # means the cache is stale and we must re-read.
        if (
            conversation_name in self._cache
            and self._cache_mtime.get(conversation_name) == current_mtime
        ):
            self._cache.move_to_end(conversation_name)
            return self._cache[conversation_name]

        if not os.path.exists(file_path):
            return []

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                if not content.strip():
                    return []
                data = json.loads(content)

                # ALWAYS clean data before validation to prevent boolean corruption
                # This is critical because pydantic_ai validation might allow boolean values
                # which will cause TypeError in Google model's _map_user_prompt
                cleaned_data = self._clean_corrupted_content(data)

                # Filter out empty responses (responses with no parts) before validation
                # Empty responses can cause "invalid message content type: <nil>" errors
                # with certain models like GLM-5 via Ollama
                filtered_data = self._filter_empty_responses(cleaned_data)

                messages = ModelMessagesTypeAdapter.validate_python(filtered_data)
                self._cache[conversation_name] = messages
                self._cache.move_to_end(conversation_name)
                self._cache_mtime[conversation_name] = current_mtime
                self._evict_lru()
                return messages

        except ValidationError as e:
            # If validation fails even after cleaning, log and return empty
            zrb_print(
                f"Warning: Failed to load history for {conversation_name} even after cleanup: {e}",
                plain=True,
            )
            return []

        except (json.JSONDecodeError, OSError) as e:
            # Log error or warn? For now, return empty list or re-raise.
            # Returning empty list is safer for UI not to crash.
            zrb_print(
                f"Warning: Failed to load history for {conversation_name}: {e}",
                plain=True,
            )
            return []

    def update(self, conversation_name: str, messages: "list[ModelMessage]"):
        self._cache[conversation_name] = messages
        self._cache.move_to_end(conversation_name)
        self._dirty.add(conversation_name)
        # Record the current file mtime as the sync point so a subsequent load()
        # against an unchanged file returns this in-memory update rather than
        # re-reading stale disk content.
        self._cache_mtime[conversation_name] = self._file_mtime(
            self._get_file_path(conversation_name)
        )
        self._evict_lru()

    def _evict_lru(self):
        """Drop least-recently-used clean cache entries beyond the bound.

        Dirty entries (updated but not yet saved) are skipped: their content
        exists only in memory, so evicting them would lose data. Clean
        entries reload losslessly from disk on next access.
        """
        while len(self._cache) > _MAX_CACHED_CONVERSATIONS:
            victim = next((k for k in self._cache if k not in self._dirty), None)
            if victim is None:
                return
            self._cache.pop(victim, None)
            self._cache_mtime.pop(victim, None)

    @staticmethod
    def _file_mtime(file_path: str) -> float | None:
        try:
            return os.path.getmtime(file_path)
        except OSError:
            return None

    def save(self, conversation_name: str, write_backup: bool = True):
        # lazy: heavy third-party
        from pydantic import ValidationError
        from pydantic_ai.messages import ModelMessagesTypeAdapter

        if conversation_name not in self._cache:
            return

        messages = self._cache[conversation_name]
        file_path = self._get_file_path(conversation_name)

        try:
            # Suppress Pydantic serialization warnings for BinaryContent in parts
            # (pydantic-ai's type adapter schema doesn't include BinaryContent in its
            # union, but serialization still works correctly)

            with warnings.catch_warnings():
                warnings.filterwarnings(
                    "ignore",
                    message="Pydantic serializer warnings",
                    category=UserWarning,
                )
                data = ModelMessagesTypeAdapter.dump_python(messages, mode="json")

            # ALWAYS clean data before saving to prevent boolean corruption
            # This ensures that even if pydantic_ai validation allows boolean values,
            # we convert them to strings before saving to disk
            cleaned_data = self._clean_corrupted_content(data)

            # Filter out empty responses before saving to prevent future issues
            # Empty responses can cause "invalid message content type: <nil>" errors
            # with certain models like GLM-5 via Ollama
            filtered_data = self._filter_empty_responses(cleaned_data)

            ModelMessagesTypeAdapter.validate_python(filtered_data)

            if not self._save_data_to_file(file_path, filtered_data):
                # Write failed (already logged by _save_data_to_file): keep the
                # entry dirty and its mtime unrefreshed so it's never mistaken
                # for safely persisted and evicted from the cache.
                return
            # Refresh the sync point so our own write doesn't look like an
            # out-of-band change on the next load().
            self._cache_mtime[conversation_name] = self._file_mtime(file_path)
            # Disk now matches the cache: the entry is evictable again.
            self._dirty.discard(conversation_name)

            # Retention is controlled by LLM_HISTORY_BACKUP_RETAIN:
            #   0  → backups disabled entirely
            #  -1  → keep every backup
            #   N  → keep the N most recent backups per conversation base name
            # write_backup=False (mid-turn checkpoint saves) skips this
            # regardless of retention — a backup per tool call would spam the
            # history dir with near-duplicate snapshots for no benefit.
            backup_retain = CFG.LLM_HISTORY_BACKUP_RETAIN
            if write_backup and backup_retain != 0:
                base_name = self._extract_base_name(conversation_name)
                timestamp = datetime.now()
                backup_path = self._get_backup_file_path(base_name, timestamp)
                if backup_path:
                    self._save_data_to_file(backup_path, filtered_data)
                    if backup_retain > 0:
                        self._rotate_backups(
                            base_name,
                            keep=backup_retain,
                            main_file_name=os.path.basename(file_path),
                        )

        except ValidationError as e:
            # If validation fails even after cleaning, log and don't save
            zrb_print(
                f"Warning: Failed to save history for {conversation_name} due to validation error: {e}",
                plain=True,
            )

        except OSError as e:
            zrb_print(
                f"Error: Failed to save history for {conversation_name}: {e}",
                plain=True,
            )

    def search(self, keyword: str) -> list[str]:
        if not os.path.exists(self._history_dir):
            return []

        matches = []
        # Delegated transcripts live in subagent/{agent_type}/ subdirectories;
        # scan those alongside the history root (which may still hold legacy
        # flat delegated files) so search sees every conversation.
        for directory in subagent_history_directories(self._history_dir):
            for filename in os.listdir(directory):
                if not filename.endswith(".json"):
                    continue

                conversation_name = filename[:-5]

                is_match, score = fuzzy_match(conversation_name, keyword)
                if is_match:
                    mtime = self._file_mtime(os.path.join(directory, filename))
                    matches.append((conversation_name, score, mtime or 0.0))

        # Sort by fuzzy score (lower is better), then most-recently-modified
        # first. With an empty keyword every score is 0.0, so the effective
        # order is mtime-descending — recent sessions surface first in `/load`.
        matches.sort(key=lambda x: (x[1], -x[2]))

        return [m[0] for m in matches]

    # ------------------------------------------------------------------
    # Part-cleaner helpers for _clean_corrupted_content
    # ------------------------------------------------------------------

    # Each cleaner starts from a copy of the original part and only normalizes
    # the field(s) that can be corrupted (chiefly ``content``). Fields the
    # cleaner does not understand are preserved verbatim — dropping them would
    # silently strip structurally-significant data such as a ThinkingPart's
    # ``signature`` (Anthropic uses it to validate replayed thinking blocks) or
    # a RetryPromptPart's ``tool_name``/``tool_call_id`` (its tool linkage).
    def _clean_user_prompt_part(self, data: dict[str, Any]) -> dict[str, Any]:
        content = data.get("content")
        if content is None:
            content = ""
        elif isinstance(content, list):
            if any(not isinstance(item, str) for item in content):
                content = to_string(content)
        elif not isinstance(content, str):
            content = to_string(content)
        return {**data, "part_kind": "user-prompt", "content": content}

    def _clean_text_like_part(
        self, part_kind: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        content = data.get("content")
        if not isinstance(content, str):
            content = to_string(content) if content is not None else ""
        return {**data, "part_kind": part_kind, "content": content}

    def _clean_tool_return_part(self, data: dict[str, Any]) -> dict[str, Any]:
        content = data.get("content")
        if content is None:
            content = ""
        res = {**data, "part_kind": "tool-return", "content": content}
        if not res.get("tool_name"):
            res["tool_name"] = "unknown"
        # Drop null/empty correlation fields that would fail provider validation,
        # while leaving any genuine value (and all other fields) untouched.
        if not res.get("tool_call_id"):
            res.pop("tool_call_id", None)
        if not res.get("timestamp"):
            res.pop("timestamp", None)
        return res

    def _clean_tool_call_part(self, data: dict[str, Any]) -> dict[str, Any] | None:
        tool_name = data.get("tool_name")
        if tool_name is None:
            return None
        res = {**data, "part_kind": "tool-call", "tool_name": tool_name}
        if res.get("args") is None:
            res["args"] = {}
        if not res.get("tool_call_id"):
            res.pop("tool_call_id", None)
        return res

    def _clean_corrupted_content(self, data: Any) -> Any:
        """Recursively clean corrupted content in message data."""
        if isinstance(data, dict):
            part_kind = data.get("part_kind")
            if part_kind == "user-prompt":
                return self._clean_user_prompt_part(data)
            if part_kind in ("text", "system-prompt", "thinking", "retry-prompt"):
                return self._clean_text_like_part(part_kind, data)
            if part_kind == "tool-return":
                return self._clean_tool_return_part(data)
            if part_kind == "tool-call":
                return self._clean_tool_call_part(data)
            return {
                k: self._clean_corrupted_content(v)
                for k, v in data.items()
                if v is not None
            }
        if isinstance(data, list):
            return [
                item
                for item in (self._clean_corrupted_content(i) for i in data)
                if item is not None
            ]
        return data

    def _is_valid_message_part(self, part: Any) -> bool:
        """Check if a message part is non-empty and valid."""
        if not isinstance(part, dict):
            return part is not None
        part_kind = part.get("part_kind")
        if part_kind == "tool-call":
            return part.get("tool_name") is not None
        if "content" in part:
            content = part.get("content")
            return content is not None and content != ""
        return part_kind is not None

    def _filter_empty_responses(self, data: Any) -> Any:
        """Filter out empty responses and parts with null content from history data."""
        if isinstance(data, list):
            filtered = []
            for item in data:
                if isinstance(item, dict):
                    kind = item.get("kind")
                    parts = item.get("parts")
                    if kind in ("response", "request") and isinstance(parts, list):
                        filtered_parts = [
                            p for p in parts if self._is_valid_message_part(p)
                        ]
                        item = {**item, "parts": filtered_parts}
                        if len(filtered_parts) == 0:
                            continue
                    item = {k: self._filter_empty_responses(v) for k, v in item.items()}
                    filtered.append(item)
                else:
                    filtered.append(self._filter_empty_responses(item))
            return filtered
        if isinstance(data, dict):
            return {
                k: v
                for k, v in (
                    (k, self._filter_empty_responses(v)) for k, v in data.items()
                )
                if v is not None
            }
        return data

    def _resolve_read_path(self, conversation_name: str) -> tuple[str, float | None]:
        """The file to read *conversation_name* from, and its mtime.

        Delegated transcripts live under ``subagent/{agent_type}/``; a name
        that resolves to the new location but has no file there falls back to
        the legacy flat history root (pre-layout files stay resumable, without
        migrating them).
        """
        file_path = self._get_file_path(conversation_name)
        mtime = self._file_mtime(file_path)
        if mtime is not None:
            return file_path, mtime
        legacy_path = self._get_legacy_file_path(conversation_name)
        if os.path.exists(legacy_path):
            return legacy_path, self._file_mtime(legacy_path)
        return file_path, None

    def _get_legacy_file_path(self, conversation_name: str) -> str:
        """The pre-`subagent/`-layout location for a delegated transcript:
        flat in the history root, next to ordinary sessions."""
        return os.path.join(
            self._history_dir, f"{_safe_segment(conversation_name)}.json"
        )

    def _get_file_path(self, conversation_name: str) -> str:
        safe_name = _safe_segment(conversation_name)
        delegated = parse_delegated_session(safe_name)
        if delegated is not None:
            # Delegated sub-agent transcripts live in their own per-agent-type
            # directory so a history listing/backup/prune never mixes them
            # with ordinary sessions (and vice versa).
            return os.path.join(
                self._history_dir,
                SUBAGENT_HISTORY_SUBDIR,
                _safe_segment(delegated[1]),
                f"{safe_name}.json",
            )
        return os.path.join(self._history_dir, f"{safe_name}.json")

    def _extract_base_name(self, conversation_name: str) -> str:
        """Extract base session name by removing timestamp suffix if present.

        For example:
        - "my-session-2024-03-18-10-30-00" -> "my-session"
        - "my-session-2024-03-18-10-30" -> "my-session"
        - "my-session" -> "my-session"
        """
        return _TIMESTAMP_PATTERN.sub("", conversation_name)

    def _get_backup_file_path(self, base_name: str, timestamp: datetime) -> str:
        """Get a backup file path with timestamp, handling conflicts.

        A backup lands next to the conversation's main file (the same
        directory `_get_file_path` resolves — the `subagent/{agent_type}/`
        dir for a delegated transcript, the history root otherwise).
        Creates files like: <name>-2024-03-18-10-30-00.json
        If that exists: <name>-2024-03-18-10-30-00-1.json
        If that exists: <name>-2024-03-18-10-30-00-2.json
        etc.
        """
        ts_str = timestamp.strftime("%Y-%m-%d-%H-%M-%S")
        base_path = os.path.join(
            os.path.dirname(self._get_file_path(base_name)), f"{base_name}-{ts_str}"
        )

        candidate = f"{base_path}.json"
        if not os.path.exists(candidate):
            return candidate

        counter = 1
        while True:
            candidate = f"{base_path}-{counter}.json"
            if not os.path.exists(candidate):
                return candidate
            counter += 1
            if counter > 1000:
                # Fallback to using microseconds
                ts_str_with_us = timestamp.strftime("%Y-%m-%d-%H-%M-%S-%f")
                return f"{base_path}-{ts_str_with_us}.json"

    def _save_data_to_file(self, file_path: str, data: Any) -> bool:
        """Save filtered data to a file.

        Returns True if successful, False otherwise. Writes to a sibling temp
        file and renames into place — truncate-writing the live conversation
        file directly means a crash mid-write corrupts the whole history.
        """
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        tmp_path = f"{file_path}.tmp"
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp_path, file_path)
            return True
        except OSError as e:
            zrb_print(f"Error: Failed to save history to {file_path}: {e}", plain=True)
            try:
                os.remove(tmp_path)
            except OSError:
                pass
            return False

    def _rotate_backups(
        self, base_name: str, keep: int, main_file_name: str | None = None
    ) -> None:
        """Delete older timestamped backups, keeping the *keep* most recent.

        A no-op when *keep* is negative (unlimited retention) or zero (backups
        disabled — no rotation needed because none are written). Errors during
        cleanup are swallowed; backup hygiene must not break a successful save.

        *main_file_name* (the live conversation file's basename) is always
        excluded: when a conversation name itself carries a timestamp suffix
        (e.g. ``session-2024-03-18-10-30``), the main file matches the backup
        filename pattern with the same base, and rotation would otherwise sort
        it oldest and delete the live history.
        """
        if keep < 0:
            return
        directory = os.path.dirname(self._get_file_path(base_name))
        try:
            entries = os.listdir(directory)
        except OSError:
            return
        backups: list[str] = []
        for name in entries:
            if main_file_name is not None and name == main_file_name:
                continue
            match = _BACKUP_FILENAME_PATTERN.match(name)
            if match and match.group("base") == base_name:
                backups.append(name)
        if len(backups) <= keep:
            return
        # Sort by filename descending (lexicographic = chronological for ISO-8601
        # timestamps). More deterministic than mtime on filesystems with coarse
        # granularity (FAT32, Docker overlayfs).
        backups.sort(reverse=True)
        for name in backups[keep:]:
            full = os.path.join(directory, name)
            try:
                os.remove(full)
            except OSError:
                continue
